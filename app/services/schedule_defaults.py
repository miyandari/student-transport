"""راننده و خودروی پیش‌فرض برنامه‌های زمانی.

- validate_schedule_defaults : اعتبارسنجی راننده/خودرو با قرارداد سرویس (هنگام ثبت پیش‌فرض)
- try_assign_defaults        : اعمال پیش‌فرض روی یک سفر (تخصیص primary با ثبت‌کننده‌ی «سیستم»)
- apply_defaults_to_future_trips : اعمال پیش‌فرض فعلی روی سفرهای آینده‌ی هنوز شروع‌نشده

تخصیص‌های موردی از نوع substitute (مثلاً راننده‌ی علی‌البدل برای یک روز) هرگز بازنویسی نمی‌شوند.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.audit_actions import AuditActions
from app.models.contract import Contract
from app.models.schedule import Schedule
from app.models.service import Service
from app.models.trip import Trip
from app.models.trip_assignment import TripAssignment
from app.models.user import User
from app.services.audit_service import create_audit_log
from app.services.trip_assignment_service import get_active_assignment, replace_active_assignment

DEFAULT_REASON = "تخصیص پیش‌فرض برنامه زمانی"


def iran_today() -> date:
    """تاریخ امروز به وقت ایران (بدون DST؛ همسو با بقیه‌ی سرویس‌ها)."""
    return (datetime.utcnow() + timedelta(hours=3, minutes=30)).date()


def _contract_of(db: Session, service: Service) -> Contract:
    contract = db.query(Contract).filter(Contract.id == service.contract_id).first() if service.contract_id else None
    if contract is None:
        raise HTTPException(400, "این سرویس به قرارداد متصل نیست؛ ابتدا قرارداد سرویس را مشخص کنید")
    return contract


def _validators():
    # import تأخیری: ماژول API در زمان import به این سرویس وابسته است
    from app.api.trip_assignments import validate_driver_for_trip, validate_vehicle_for_trip
    return validate_driver_for_trip, validate_vehicle_for_trip


def validate_schedule_defaults(db: Session, *, service: Service, driver_id: int | None, vehicle_id: int | None) -> None:
    """خطای 400 اگر راننده/خودرو فعال نباشد یا به قرارداد سرویس تخصیص نیافته باشد."""
    if driver_id is None and vehicle_id is None:
        return
    check_driver, check_vehicle = _validators()
    contract = _contract_of(db, service)
    probe = SimpleNamespace(university_id=service.university_id, trip_date=iran_today())
    check_driver(db, probe, contract, driver_id)
    check_vehicle(db, probe, contract, vehicle_id)


def try_assign_defaults(db: Session, trip: Trip, schedule: Schedule, contract: Contract, user: User | None = None) -> str:
    """نتیجه: none (پیش‌فرضی نیست) | invalid (پیش‌فرض دیگر معتبر نیست) | partial | assigned"""
    driver_id, vehicle_id = schedule.default_driver_id, schedule.default_vehicle_id
    if driver_id is None and vehicle_id is None:
        return "none"
    check_driver, check_vehicle = _validators()
    dropped = False
    try:
        check_driver(db, trip, contract, driver_id)
    except HTTPException:
        driver_id, dropped = None, True
    try:
        check_vehicle(db, trip, contract, vehicle_id)
    except HTTPException:
        vehicle_id, dropped = None, True
    if driver_id is None and vehicle_id is None:
        return "invalid"
    assignment = TripAssignment(
        trip_id=trip.id, driver_id=driver_id, vehicle_id=vehicle_id,
        assigned_by_user_id=user.id if user else None,
        assignment_type="primary", reason=DEFAULT_REASON, start_at=None, end_at=None, is_active=False,
    )
    db.add(assignment)
    db.flush()
    replace_active_assignment(db, trip, assignment)
    create_audit_log(
        db, user=user, action=AuditActions.ASSIGN, entity_type="TripAssignment", entity_id=assignment.id,
        description=DEFAULT_REASON,
        new_values={"trip_id": trip.id, "driver_id": driver_id, "vehicle_id": vehicle_id, "schedule_id": schedule.id},
    )
    return "partial" if dropped or driver_id is None or vehicle_id is None else "assigned"


def apply_defaults_to_future_trips(db: Session, schedule: Schedule, user: User | None) -> dict:
    """پیش‌فرض فعلی را روی سفرهای scheduled از امروز به بعد اعمال می‌کند (بدون commit)."""
    result = {"updated": 0, "unchanged": 0, "skipped_substitute": 0, "invalid": 0, "total": 0}
    if schedule.default_driver_id is None and schedule.default_vehicle_id is None:
        return result
    service = db.query(Service).filter(Service.id == schedule.service_id).first()
    contract = _contract_of(db, service)
    trips = (
        db.query(Trip)
        .filter(Trip.schedule_id == schedule.id, Trip.trip_date >= iran_today(), Trip.status == "scheduled", Trip.is_active.is_(True))
        .order_by(Trip.trip_date)
        .all()
    )
    for trip in trips:
        result["total"] += 1
        active = get_active_assignment(db, trip.id)
        if active is not None and active.assignment_type == "substitute":
            result["skipped_substitute"] += 1
            continue
        if trip.driver_id == schedule.default_driver_id and trip.vehicle_id == schedule.default_vehicle_id:
            result["unchanged"] += 1
            continue
        outcome = try_assign_defaults(db, trip, schedule, contract, user)
        result["invalid" if outcome in ("invalid", "none") else "updated"] += 1
    return result
