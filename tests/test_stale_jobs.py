from datetime import datetime, timedelta, timezone

from app.jobs.close_stale_trips import run
from app.models.trip import Trip


def test_stale_scheduled_trip_is_cancelled_and_running_completed(db, make_trip):
    old = datetime.now(timezone.utc) - timedelta(days=1)
    a = make_trip(seated=3, status="scheduled")
    b = make_trip(seated=3, status="in_progress")
    for t in (a, b):
        t.planned_departure_time = old
        t.trip_date = old.date()
    b.actual_departure_time = old
    db.commit()
    ids = (a.id, b.id)

    assert run(3, 12) == 0
    db.expire_all()
    assert db.get(Trip, ids[0]).status == "cancelled"
    assert db.get(Trip, ids[1]).status == "completed"
