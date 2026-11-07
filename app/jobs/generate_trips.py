"""تولید خودکار سفرهای روزهای آینده (برای اجرای زمان‌بندی‌شده با cron / systemd timer / Docker).

    python -m app.jobs.generate_trips                 # فردا، همه‌ی دانشگاه‌های فعال
    python -m app.jobs.generate_trips --days 3        # ۳ روز آینده (از فردا)
    python -m app.jobs.generate_trips --university-id 2
    python -m app.jobs.generate_trips --date 2026-11-10

تکرار اجرا بی‌خطر است: سفرِ موجود دوباره ساخته نمی‌شود.
کد خروج: ۰ موفق، ۱ اگر برای دست‌کم یک دانشگاه خطا رخ داده باشد.
"""
import argparse
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.models.university import University
from app.services.schedule_defaults import iran_today
from app.services.trip_service import generate_daily_trips


def run(days: int, university_id: int | None, only_date: date | None) -> int:
    dates = [only_date] if only_date else [iran_today() + timedelta(days=i) for i in range(1, days + 1)]
    failures = 0
    with SessionLocal() as probe:
        q = probe.query(University.id, University.name).filter(University.is_active.is_(True))
        if university_id is not None:
            q = q.filter(University.id == university_id)
        unis = q.order_by(University.id).all()
    if not unis:
        print("دانشگاه فعالی پیدا نشد")
        return 1
    for uid, name in unis:
        for d in dates:
            db = SessionLocal()
            try:
                trips = generate_daily_trips(db=db, university_id=uid, trip_date=d)
                assigned = sum(1 for t in trips if t.driver_id and t.vehicle_id)
                print(f"[{name}] {d}: {len(trips)} سفر ساخته شد ({assigned} با راننده و خودرو، {len(trips) - assigned} بدون تخصیص کامل)")
            except Exception as e:  # یک دانشگاه نباید بقیه را متوقف کند
                failures += 1
                print(f"[{name}] {d}: خطا — {getattr(e, 'detail', e)}", file=sys.stderr)
                db.rollback()
            finally:
                db.close()
    return 1 if failures else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=1, help="چند روز آینده (از فردا)؛ پیش‌فرض ۱")
    ap.add_argument("--university-id", type=int, default=None)
    ap.add_argument("--date", type=date.fromisoformat, default=None, help="فقط همین تاریخ (YYYY-MM-DD)")
    a = ap.parse_args()
    if a.days < 1 or a.days > 31:
        ap.error("--days باید بین ۱ و ۳۱ باشد")
    sys.exit(run(a.days, a.university_id, a.date))


if __name__ == "__main__":
    main()
