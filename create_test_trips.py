"""
ساخت سفرهای آزمایشی روی داده‌ی واقعی خودتان (برای بررسی دستی اپ‌ها).

    python create_test_trips.py                      # فهرست دانشگاه‌ها
    python create_test_trips.py --university-id 1    # ساخت سفرهای آزمایشی امروز
    python create_test_trips.py --university-id 1 --reset   # حذف سفرهای آزمایشی

برای تا ۴ سرویس فعال دانشگاه، سناریوهای زیر ساخته می‌شود (ساعت‌ها نسبت به «الان»):
  ۱) عادی           : ۹۰ دقیقه بعد، راننده+خودرو، جای خالی دارد            → رزرو موفق
  ۲) پر             : ۱۲۰ دقیقه بعد، ظرفیت ۱ و یک نفر رزرو دارد           → پیام «با تأیید راننده»
  ۳) بدون ظرفیت     : ۱۵۰ دقیقه بعد، راننده دارد ولی خودرو/ظرفیت ندارد    → مثل پر
  ۴) بدون راننده    : ۱۸۰ دقیقه بعد، راننده ندارد                          → در اپ دانشجو دیده نمی‌شود
  ۵) در حال سوارشدن : ۵ دقیقه قبل، وضعیت boarding                          → تست اسکن QR توسط راننده

سفرهای آزمایشی با «ثانیه‌ی ۱۳» در ساعت حرکت علامت‌گذاری می‌شوند و --reset فقط همان‌ها را
(با رزرو/مسافر/درخواست‌های وابسته) پاک می‌کند. به سفرهای واقعی دست نمی‌زند.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.boarding_request import BoardingRequest
from app.models.driver import Driver
from app.models.feedback import Feedback
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.service import Service
from app.models.station_event import StationEvent
from app.models.student import Student
from app.models.trip import Trip
from app.models.trip_assignment import TripAssignment
from app.models.trip_incident import TripIncident
from app.models.trip_passenger import TripPassenger
from app.models.university import University
from app.models.vehicle import Vehicle
from app.models.vehicle_location import VehicleLocation

MARK_SECOND = 13


def _is_test(trip: Trip) -> bool:
    return trip.planned_departure_time.second == MARK_SECOND


def reset(db, university_id: int) -> int:
    ids = [t.id for t in db.query(Trip).filter(Trip.university_id == university_id) if _is_test(t)]
    if not ids:
        return 0
    for model in (VehicleLocation, StationEvent, TripIncident, TripAssignment,
                  BoardingRequest, TripPassenger, Feedback, Reservation):
        db.query(model).filter(model.trip_id.in_(ids)).delete(synchronize_session=False)
    db.query(Trip).filter(Trip.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return len(ids)


def build(db, university_id: int) -> None:
    services = (
        db.query(Service)
        .filter(Service.university_id == university_id, Service.is_active.is_(True))
        .order_by(Service.id)
        .limit(4)
        .all()
    )
    drivers = db.query(Driver).filter(Driver.university_id == university_id, Driver.is_active.is_(True)).order_by(Driver.id).all()
    vehicles = db.query(Vehicle).filter(Vehicle.university_id == university_id, Vehicle.is_active.is_(True)).order_by(Vehicle.id).all()
    if not services or not drivers or not vehicles:
        sys.exit("دانشگاه باید حداقل یک سرویس فعال، یک راننده و یک خودرو فعال داشته باشد.")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    n = 0

    def planned(minutes: int) -> datetime:
        return (now + timedelta(minutes=minutes)).replace(second=MARK_SECOND)

    def add_trip(service, minutes, status, *, driver=None, vehicle=None, seated=None, standing=0):
        nonlocal n
        dep = planned(minutes)
        trip = Trip(
            university_id=university_id, service_id=service.id,
            driver_id=driver.id if driver else None, vehicle_id=vehicle.id if vehicle else None,
            seated_capacity=seated, standing_capacity=standing or None,
            allow_standing=standing > 0,
            trip_date=dep.astimezone(timezone(timedelta(hours=3, minutes=30))).date(),
            planned_departure_time=dep, status=status, is_active=True,
        )
        db.add(trip)
        db.flush()
        if driver or vehicle:
            db.add(TripAssignment(
                trip_id=trip.id, driver_id=driver.id if driver else None,
                vehicle_id=vehicle.id if vehicle else None, assigned_by_user_id=None,
                assignment_type="primary", reason="سفر آزمایشی", start_at=dep, is_active=True,
            ))
        n += 1
        return trip

    for i, service in enumerate(services):
        d = drivers[i % len(drivers)]
        v = vehicles[i % len(vehicles)]
        gender = (service.gender_restriction or "mixed").lower()
        cap = v.capacity or 20

        add_trip(service, 90 + i * 7, "scheduled", driver=d, vehicle=v, seated=cap, standing=0)

        full = add_trip(service, 120 + i * 7, "scheduled", driver=d, vehicle=v, seated=1)
        student = (
            db.query(Student)
            .filter(Student.university_id == university_id, Student.is_active.is_(True))
            .filter(True if gender == "mixed" else Student.gender == gender)
            .order_by(Student.id).first()
        )
        if student:
            db.add(Reservation(trip_id=full.id, student_id=student.id, status="active",
                               is_standing=False, reservation_time=now))

        add_trip(service, 150 + i * 7, "scheduled", driver=d)  # بدون خودرو/ظرفیت
        add_trip(service, 180 + i * 7, "scheduled")             # بدون راننده
        add_trip(service, -5 - i * 7, "boarding", driver=d, vehicle=v, seated=cap, standing=2)

    db.commit()
    print(f"{n} سفر آزمایشی ساخته شد ({len(services)} سرویس × ۵ سناریو).")
    print("حذف: python create_test_trips.py --university-id", university_id, "--reset")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--university-id", type=int)
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        if a.university_id is None:
            for u in db.query(University).order_by(University.id):
                print(f"{u.id}\t{u.name}")
            return
        removed = reset(db, a.university_id)
        if a.reset:
            print(f"{removed} سفر آزمایشی حذف شد.")
            return
        if removed:
            print(f"{removed} سفر آزمایشی قبلی حذف شد.")
        build(db, a.university_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
