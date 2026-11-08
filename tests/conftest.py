"""
تست‌ها با SQLite موقت اجرا می‌شوند (نیازی به PostgreSQL نیست).
توجه: with_for_update در SQLite بی‌اثر است؛ تست رقابت واقعی همزمان باید روی PostgreSQL اجرا شود.
"""
import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: F401,E402


@pytest.fixture(scope="session", autouse=True)
def _seed():
    Base.metadata.create_all(engine)
    import create_demo_data  # noqa: F401  (اجرا هنگام import انجام می‌شود)
    yield


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def make_trip(db):
    """ساخت سفر جدید با ظرفیت دلخواه بر پایه‌ی سرویس/راننده‌ی دمو."""
    from app.models.trip import Trip

    created = []

    def _make(seated=2, standing=0, status="boarding"):
        base = db.query(Trip).filter(Trip.service_id.isnot(None)).first()
        t = Trip(
            university_id=base.university_id, service_id=base.service_id,
            driver_id=base.driver_id, vehicle_id=base.vehicle_id,
            seated_capacity=seated, standing_capacity=standing or None,
            allow_standing=standing > 0,
            trip_date=date.today() + timedelta(days=30),
            planned_departure_time=datetime.now(timezone.utc) + timedelta(days=30),
            status=status, is_active=True,
        )
        db.add(t)
        db.commit()
        created.append(t.id)
        return t

    return _make


@pytest.fixture()
def students(db, make_trip):
    """دانشجویان دمو هم‌جنس با سرویس سفر (جنسیت mixed فرض نمی‌شود)."""
    from app.models.student import Student
    from app.models.university import University

    uni = db.query(University).filter(University.code == "DEMO-UT").one()
    return db.query(Student).filter(Student.university_id == uni.id).order_by(Student.id).all()
