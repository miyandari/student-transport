"""بستن سفرهای بلاتکلیف (برای اجرای زمان‌بندی‌شده، مثلاً هر ساعت با cron).

    python -m app.jobs.close_stale_trips
    python -m app.jobs.close_stale_trips --scheduled-hours 3 --running-hours 12

- سفر scheduled/boarding که بیش از N ساعت از زمان برنامه‌اش گذشته و هرگز شروع نشده → لغو
  (رزروها و درخواست‌های pending لغو و به دانشجویان اعلان می‌شود؛ جریمه ثبت نمی‌شود).
- سفر in_progress که بیش از M ساعت از زمان برنامه‌اش گذشته → تکمیل
  (عدم‌حضورها طبق روال عادی ثبت می‌شود).
تکرار اجرا بی‌خطر است.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.trip import Trip
from app.services.trip_service import update_trip_status


def run(scheduled_hours: int, running_hours: int) -> int:
    now = datetime.now(timezone.utc)
    failures = 0
    with SessionLocal() as probe:
        stale = [
            (t.id, t.status)
            for t in probe.query(Trip.id, Trip.status, Trip.planned_departure_time)
            .filter(Trip.status.in_(["scheduled", "boarding", "in_progress"]))
            .all()
            if _age(now, t.planned_departure_time)
            > timedelta(hours=running_hours if t.status == "in_progress" else scheduled_hours)
        ]
    for trip_id, status in stale:
        db = SessionLocal()
        try:
            trip = db.get(Trip, trip_id)
            if trip is None or trip.status != status:
                continue
            target = "completed" if status == "in_progress" else "cancelled"
            update_trip_status(db, trip, target)
            print(f"سفر {trip_id}: {status} → {target}")
        except Exception as e:  # یک سفر نباید بقیه را متوقف کند
            failures += 1
            db.rollback()
            print(f"سفر {trip_id}: خطا — {getattr(e, 'detail', e)}", file=sys.stderr)
        finally:
            db.close()
    print(f"{len(stale)} سفر بلاتکلیف بررسی شد")
    return 1 if failures else 0


def _age(now: datetime, planned: datetime) -> timedelta:
    if planned.tzinfo is None:
        planned = planned.replace(tzinfo=timezone.utc)
    return now - planned


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scheduled-hours", type=int, default=3)
    ap.add_argument("--running-hours", type=int, default=12)
    a = ap.parse_args()
    sys.exit(run(a.scheduled_hours, a.running_hours))


if __name__ == "__main__":
    main()
