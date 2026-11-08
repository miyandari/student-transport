"""
endpointهای مخصوص اپ راننده (prefix: /driver).

این router را در app/main.py ثبت کنید (راهنما در BACKEND_PATCH_DRIVER.md).

راننده در بک‌اند فعلی اجازه‌ی تغییر وضعیت سفر را ندارد (PATCH /trips/{id}/status
فقط برای مدیران است). این فایل فقط همان کارهایی را به راننده می‌دهد که برای
سفر «خودش» لازم است، و هیچ دسترسی دیگری باز نمی‌کند.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.database import get_db
from app.models.boarding_request import BoardingRequest
from app.models.driver import Driver
from app.models.reservation import Reservation
from app.models.route_station import RouteStation
from app.models.station import Station
from app.models.student import Student
from app.models.trip import Trip
from app.models.trip_passenger import TripPassenger
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.notification_service import create_notification
from app.services.trip_incident_service import create_trip_incident
from app.services.trip_service import update_trip_status
from app.services.vehicle_location_service import (
    ACTIVE_LOCATION_TRIP_STATUSES,
    create_vehicle_location,
)

router = APIRouter(prefix="/driver", tags=["Driver App"])

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# راننده فقط می‌تواند سفر را به جلو ببرد؛ لغو سفر با مدیریت است.
DRIVER_STATUS_FLOW = {
    "scheduled": {"boarding"},
    "boarding": {"in_progress"},
    "in_progress": {"completed"},
}

BREAKDOWN_KINDS = {"engine", "tire", "electrical", "fuel", "accident", "other"}
MAX_POINTS_PER_BATCH = 100


# =========================================================
# Schemas
# =========================================================

class VehicleOut(BaseModel):
    id: int
    plate_number: str
    vehicle_type: str
    capacity: int


class DriverMeResponse(BaseModel):
    driver_id: int
    university_id: int
    first_name: str
    last_name: str
    phone: str | None
    vehicle: VehicleOut | None


class StopOut(BaseModel):
    station_id: int
    name: str
    latitude: float | None
    longitude: float | None
    stop_order: int
    minutes_from_start: int | None


class DriverTripOut(BaseModel):
    id: int
    service_id: int
    service_name: str
    trip_date: date
    planned_departure_time: datetime
    actual_departure_time: datetime | None
    status: str
    vehicle_id: int | None
    vehicle_plate: str | None
    seated_capacity: int | None
    standing_capacity: int | None
    reserved_count: int
    stops: list[StopOut]


class ManifestPassenger(BaseModel):
    reservation_id: int | None = None
    # سوارشده با QR بدون رزرو (با تأیید راننده)
    walk_in: bool = False
    student_id: int
    name: str
    student_number: str
    gender: str
    station_id: int | None
    station_name: str | None
    is_standing: bool
    boarded: bool


class ManifestRequest(BaseModel):
    request_id: int
    student_id: int
    name: str
    station_id: int | None
    station_name: str | None
    is_standing: bool
    requested_at: datetime


class ManifestResponse(BaseModel):
    trip_id: int
    passengers: list[ManifestPassenger]
    pending_requests: list[ManifestRequest]


class ScanBody(BaseModel):
    qr_token: str = Field(min_length=10, max_length=100)
    # true: راننده سوار شدن دانشجوی بدون رزرو را تأیید کرده است
    confirm_walk_in: bool = False
    station_id: int | None = None


class ScanResult(BaseModel):
    # boarded | already | needs_confirm | full | rejected
    result: str
    student_id: int | None = None
    name: str | None = None
    student_number: str | None = None
    has_reservation: bool = False
    message: str | None = None


class DriverStatusBody(BaseModel):
    status: str


class LocationPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: float | None = None
    heading: float | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at باید دارای timezone باشد")
        return value.astimezone(timezone.utc)


class LocationBatch(BaseModel):
    points: list[LocationPoint] = Field(min_length=1)


class LocationBatchResult(BaseModel):
    accepted: int
    rejected: int
    # false یعنی سفر دیگر در حالت ثبت موقعیت نیست؛ اپ باید ارسال را متوقف کند.
    trip_active: bool
    last_error: str | None = None


class BreakdownBody(BaseModel):
    kind: str
    description: str | None = Field(default=None, max_length=1000)
    # راننده می‌تواند با همین خودرو ادامه بدهد (مثلاً تأخیر کوتاه) یا نه.
    can_continue: bool = False
    latitude: float | None = None
    longitude: float | None = None
    occurred_at: datetime | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in BREAKDOWN_KINDS:
            raise ValueError("نوع خرابی نامعتبر است")
        return value


class BreakdownResult(BaseModel):
    incident_id: int
    notified_students: int
    notified_managers: int


# =========================================================
# Helpers
# =========================================================

def current_driver(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> tuple[User, Driver]:
    if user.role != Roles.DRIVER or user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این بخش فقط برای راننده است",
        )
    driver = db.query(Driver).filter(Driver.id == user.driver_id).first()
    if driver is None or not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب راننده فعال نیست",
        )
    return user, driver


def own_trip(db: Session, driver: Driver, trip_id: int) -> Trip:
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر پیدا نشد",
        )
    if trip.driver_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است",
        )
    return trip


def _stops(db: Session, trip: Trip) -> list[StopOut]:
    if trip.service is None:
        return []
    rows = (
        db.query(RouteStation, Station)
        .join(Station, Station.id == RouteStation.station_id)
        .filter(RouteStation.route_id == trip.service.route_id)
        .order_by(RouteStation.stop_order.asc())
        .all()
    )
    return [
        StopOut(
            station_id=st.id,
            name=st.name,
            latitude=st.latitude,
            longitude=st.longitude,
            stop_order=rs.stop_order,
            minutes_from_start=rs.estimated_minutes_from_start,
        )
        for rs, st in rows
    ]


def _trip_out(db: Session, trip: Trip) -> DriverTripOut:
    vehicle = (
        db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()
        if trip.vehicle_id
        else None
    )
    reserved = (
        db.query(Reservation)
        .filter(Reservation.trip_id == trip.id, Reservation.status == "active")
        .count()
    )
    return DriverTripOut(
        id=trip.id,
        service_id=trip.service_id,
        service_name=trip.service.name if trip.service else "",
        trip_date=trip.trip_date,
        planned_departure_time=trip.planned_departure_time,
        actual_departure_time=trip.actual_departure_time,
        status=trip.status,
        vehicle_id=trip.vehicle_id,
        vehicle_plate=vehicle.plate_number if vehicle else None,
        seated_capacity=trip.seated_capacity,
        standing_capacity=trip.standing_capacity,
        reserved_count=reserved,
        stops=_stops(db, trip),
    )


# =========================================================
# Endpoints
# =========================================================

@router.get("/me", response_model=DriverMeResponse)
def driver_me(
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    _, driver = ctx
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.driver_id == driver.id, Vehicle.is_active.is_(True))
        .first()
    )
    return DriverMeResponse(
        driver_id=driver.id,
        university_id=driver.university_id,
        first_name=driver.first_name,
        last_name=driver.last_name,
        phone=driver.phone,
        vehicle=(
            VehicleOut(
                id=vehicle.id,
                plate_number=vehicle.plate_number,
                vehicle_type=vehicle.vehicle_type,
                capacity=vehicle.capacity,
            )
            if vehicle
            else None
        ),
    )


@router.get("/trips", response_model=list[DriverTripOut])
def driver_trips(
    trip_date: date | None = Query(default=None),
    days: int = Query(default=1, ge=1, le=7),
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    """سفرهای راننده از [trip_date] (پیش‌فرض: امروز به وقت ایران) به‌مدت [days] روز."""
    _, driver = ctx
    start = trip_date or datetime.now(IRAN_TZ).date()
    end = start + timedelta(days=days - 1)

    trips = (
        db.query(Trip)
        .filter(
            Trip.driver_id == driver.id,
            Trip.is_active.is_(True),
            Trip.trip_date >= start,
            Trip.trip_date <= end,
        )
        .order_by(Trip.planned_departure_time.asc())
        .all()
    )
    return [_trip_out(db, t) for t in trips]


@router.get("/trips/{trip_id}", response_model=DriverTripOut)
def driver_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    _, driver = ctx
    return _trip_out(db, own_trip(db, driver, trip_id))


@router.post("/trips/{trip_id}/status", response_model=DriverTripOut)
def driver_trip_status(
    trip_id: int,
    body: DriverStatusBody,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    _, driver = ctx
    trip = own_trip(db, driver, trip_id)
    new_status = body.status.strip().lower()

    if new_status not in DRIVER_STATUS_FLOW.get(trip.status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تغییر وضعیت سفر به این حالت برای راننده مجاز نیست",
        )

    update_trip_status(db, trip, new_status)
    db.refresh(trip)
    return _trip_out(db, trip)


@router.get("/trips/{trip_id}/manifest", response_model=ManifestResponse)
def driver_manifest(
    trip_id: int,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    _, driver = ctx
    trip = own_trip(db, driver, trip_id)

    stations = {s.id: s.name for s in db.query(Station).filter(
        Station.university_id == trip.university_id
    )}
    boarded = {
        p.student_id
        for p in db.query(TripPassenger).filter(
            TripPassenger.trip_id == trip.id,
            TripPassenger.boarding_time.isnot(None),
        )
    }

    rows = (
        db.query(Reservation, Student)
        .join(Student, Student.id == Reservation.student_id)
        .filter(Reservation.trip_id == trip.id, Reservation.status == "active")
        .order_by(Student.last_name.asc(), Student.first_name.asc())
        .all()
    )
    passengers = [
        ManifestPassenger(
            reservation_id=r.id,
            student_id=s.id,
            name=f"{s.first_name} {s.last_name}",
            student_number=s.student_number,
            gender=s.gender,
            station_id=r.station_id,
            station_name=stations.get(r.station_id),
            is_standing=r.is_standing,
            boarded=s.id in boarded,
        )
        for r, s in rows
    ]

    reserved_ids = {r.student_id for r, _ in rows}
    walk_rows = (
        db.query(TripPassenger, Student)
        .join(Student, Student.id == TripPassenger.student_id)
        .filter(
            TripPassenger.trip_id == trip.id,
            TripPassenger.boarding_time.isnot(None),
        )
        .order_by(TripPassenger.boarding_time.asc())
        .all()
    )
    for tp, s in walk_rows:
        if s.id in reserved_ids:
            continue
        passengers.append(
            ManifestPassenger(
                reservation_id=None,
                walk_in=True,
                student_id=s.id,
                name=f"{s.first_name} {s.last_name}",
                student_number=s.student_number,
                gender=s.gender,
                station_id=tp.boarding_station_id,
                station_name=stations.get(tp.boarding_station_id),
                is_standing=bool(tp.is_standing),
                boarded=True,
            )
        )

    pending = (
        db.query(BoardingRequest, Student)
        .join(Student, Student.id == BoardingRequest.student_id)
        .filter(
            BoardingRequest.trip_id == trip.id,
            BoardingRequest.status == "pending",
        )
        .order_by(BoardingRequest.requested_at.asc())
        .all()
    )
    requests = [
        ManifestRequest(
            request_id=b.id,
            student_id=s.id,
            name=f"{s.first_name} {s.last_name}",
            station_id=b.boarding_station_id,
            station_name=stations.get(b.boarding_station_id),
            is_standing=b.is_standing,
            requested_at=b.requested_at,
        )
        for b, s in pending
    ]
    return ManifestResponse(
        trip_id=trip.id, passengers=passengers, pending_requests=requests
    )


@router.post("/trips/{trip_id}/scan", response_model=ScanResult)
def driver_scan(
    trip_id: int,
    body: ScanBody,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    """
    اسکن QR دانشجو هنگام سوار شدن.

    - رزرو فعال دارد: بی‌صدا سوار ثبت می‌شود (result=boarded).
    - قبلاً سوار شده: بی‌اثر (result=already).
    - رزرو ندارد: بدون تأیید راننده ثبت نمی‌شود (result=needs_confirm)؛
      با confirm_walk_in=true به‌عنوان مسافر بدون رزرو ثبت می‌شود.
    خطای QR نامعتبر 404 است؛ ظرفیت پر result=full و سایر رد شدن‌ها result=rejected.
    """
    from app.services.trip_passenger_service import board_passenger

    _, driver = ctx
    trip = own_trip(db, driver, trip_id)

    student = (
        db.query(Student)
        .filter(Student.qr_token == body.qr_token.strip(), Student.is_active.is_(True))
        .first()
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR کد معتبر نیست",
        )

    name = f"{student.first_name} {student.last_name}"

    def out(result: str, **kw) -> ScanResult:
        return ScanResult(
            result=result, student_id=student.id, name=name,
            student_number=student.student_number, **kw,
        )

    if student.university_id != trip.university_id:
        return out("rejected", message="این دانشجو متعلق به دانشگاه این سفر نیست")

    already = (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip.id,
            TripPassenger.student_id == student.id,
            TripPassenger.boarding_time.isnot(None),
        )
        .first()
    )
    if already is not None:
        return out("already")

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.student_id == student.id,
            Reservation.status == "active",
        )
        .first()
    )
    has_res = reservation is not None

    if not has_res and not body.confirm_walk_in:
        return out("needs_confirm", has_reservation=False)

    station_id = body.station_id or (reservation.station_id if reservation else None)
    standing = bool(reservation.is_standing) if reservation else False
    try:
        board_passenger(
            db,
            trip_id=trip.id,
            student_id=student.id,
            boarding_method="qr" if has_res else "qr_without_reservation",
            is_standing=standing,
            boarding_station_id=station_id,
        )
    except HTTPException as e:
        db.rollback()
        if e.status_code == status.HTTP_409_CONFLICT:
            return out("full", has_reservation=has_res, message=str(e.detail))
        return out("rejected", has_reservation=has_res, message=str(e.detail))
    return out("boarded", has_reservation=has_res)


@router.post("/trips/{trip_id}/locations", response_model=LocationBatchResult)
async def driver_locations(
    trip_id: int,
    body: LocationBatch,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    """ثبت دسته‌ای موقعیت‌ها (برای صف آفلاین اپ). نقطه‌ها به ترتیب زمان ثبت می‌شوند."""
    _, driver = ctx
    trip = own_trip(db, driver, trip_id)

    if len(body.points) > MAX_POINTS_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"حداکثر {MAX_POINTS_PER_BATCH} نقطه در هر درخواست",
        )

    if trip.status not in ACTIVE_LOCATION_TRIP_STATUSES or trip.vehicle_id is None:
        return LocationBatchResult(
            accepted=0, rejected=len(body.points), trip_active=False
        )

    accepted = 0
    last_error: str | None = None
    for point in sorted(body.points, key=lambda p: p.recorded_at):
        try:
            await create_vehicle_location(
                db,
                trip_id=trip.id,
                vehicle_id=trip.vehicle_id,
                latitude=point.latitude,
                longitude=point.longitude,
                speed=point.speed,
                heading=point.heading,
                recorded_at=point.recorded_at,
                driver_id=driver.id,
            )
            accepted += 1
        except HTTPException as e:
            db.rollback()
            last_error = str(e.detail)

    return LocationBatchResult(
        accepted=accepted,
        rejected=len(body.points) - accepted,
        trip_active=True,
        last_error=last_error,
    )


class DelayBody(BaseModel):
    minutes: int = Field(ge=1, le=720)
    reason: str | None = Field(default=None, max_length=500)


@router.post("/trips/{trip_id}/delay")
def driver_delay(
    trip_id: int,
    body: DelayBody,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    """اعلام تأخیر توسط راننده: ثبت حادثه + اعلان به دانشجویان رزروکننده."""
    _user, driver = ctx
    trip = own_trip(db, driver, trip_id)

    from app.services.trip_lifecycle_service import announce_trip_delay

    return announce_trip_delay(
        db,
        trip=trip,
        minutes=body.minutes,
        reason=body.reason,
        reported_by_driver_id=driver.id,
    )


@router.post("/trips/{trip_id}/breakdown", response_model=BreakdownResult)
def driver_breakdown(
    trip_id: int,
    body: BreakdownBody,
    db: Session = Depends(get_db),
    ctx: tuple[User, Driver] = Depends(current_driver),
):
    """اعلام خرابی خودرو: ثبت حادثه + اعلان به مدیران و دانشجوهای رزروکرده."""
    user, driver = ctx
    trip = own_trip(db, driver, trip_id)

    parts = []
    if body.description:
        parts.append(body.description.strip())
    parts.append(
        "ادامه‌ی سفر با همین خودرو ممکن است."
        if body.can_continue
        else "ادامه‌ی سفر با همین خودرو ممکن نیست؛ جایگزین لازم است."
    )
    if body.latitude is not None and body.longitude is not None:
        parts.append(f"موقعیت: {body.latitude:.5f}, {body.longitude:.5f}")

    incident = create_trip_incident(
        db,
        trip_id=trip.id,
        reported_by_driver_id=driver.id,
        incident_type=f"vehicle_breakdown:{body.kind}",
        description="\n".join(parts),
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
    )

    service_name = trip.service.name if trip.service else ""
    data = {
        "trip_id": trip.id,
        "incident_id": incident.id,
        "kind": body.kind,
        "can_continue": body.can_continue,
    }

    managers = (
        db.query(User)
        .filter(
            User.university_id == trip.university_id,
            User.role.in_([Roles.UNIVERSITY_ADMIN, Roles.TRANSPORT_MANAGER]),
            User.is_active.is_(True),
        )
        .all()
    )
    for m in managers:
        create_notification(
            db,
            user_id=m.id,
            university_id=trip.university_id,
            notification_type="trip_breakdown_manager",
            title="اعلام خرابی خودرو",
            message=(
                f"راننده {driver.first_name} {driver.last_name} برای سفر "
                f"«{service_name}» خرابی اعلام کرد."
            ),
            data=data,
        )

    student_users = (
        db.query(User)
        .join(Reservation, Reservation.student_id == User.student_id)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status == "active",
            User.is_active.is_(True),
        )
        .all()
    )
    student_msg = (
        "سرویس شما دچار مشکل شده و ممکن است با تأخیر برسد."
        if body.can_continue
        else "سرویس شما دچار خرابی شده است؛ جایگزین در حال پیگیری است."
    )
    for su in student_users:
        create_notification(
            db,
            user_id=su.id,
            university_id=su.university_id,
            notification_type="trip_breakdown",
            title="خرابی سرویس",
            message=f"{student_msg} ({service_name})",
            data=data,
        )

    db.commit()
    return BreakdownResult(
        incident_id=incident.id,
        notified_students=len(student_users),
        notified_managers=len(managers),
    )
