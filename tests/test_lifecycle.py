from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.trip_incident import TripIncident

client = TestClient(app)


def _h(username, password):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _reserved_trip(db, make_trip, students):
    trip = make_trip(seated=5, status="scheduled")
    r = (trip.service.gender_restriction or "mixed").lower()
    st = [s for s in students if r == "mixed" or s.gender == r][0]
    db.add(Reservation(trip_id=trip.id, student_id=st.id, status="active", is_standing=False,
                       reservation_time=datetime.now(timezone.utc)))
    db.commit()
    return trip


def test_admin_delay_creates_incident_and_notifies(db, make_trip, students):
    trip = _reserved_trip(db, make_trip, students)
    before = db.query(Notification).filter_by(notification_type="trip_delay").count()
    r = client.post(f"/trips/{trip.id}/delay", headers=_h("demo_admin", "Admin@Demo123"),
                    json={"minutes": 15, "reason": "ترافیک"})
    assert r.status_code == 200, r.text
    assert db.query(TripIncident).filter_by(trip_id=trip.id, incident_type="trip_delay").count() == 1
    assert r.json()["notified_students"] >= 0
    db.expire_all()
    after = db.query(Notification).filter_by(notification_type="trip_delay").count()
    assert after - before == r.json()["notified_students"]


def test_driver_delay_only_own_trip(db, make_trip, students):
    from app.models.driver import Driver
    trip = _reserved_trip(db, make_trip, students)
    owner = db.get(Driver, trip.driver_id)
    from app.models.user import User
    u = db.query(User).filter_by(driver_id=owner.id).first()
    assert u is not None
    r = client.post(f"/driver/trips/{trip.id}/delay", headers=_h(u.username, "Driver@123"),
                    json={"minutes": 10})
    assert r.status_code == 200, r.text
    other = db.query(User).filter(User.driver_id.isnot(None), User.driver_id != owner.id).first()
    r2 = client.post(f"/driver/trips/{trip.id}/delay", headers=_h(other.username, "Driver@123"),
                     json={"minutes": 10})
    assert r2.status_code == 403


def test_replacement_notifies_new_driver_and_students(db, make_trip, students):
    from app.models.driver import Driver
    from app.models.user import User
    from app.services.trip_incident_service import create_trip_incident, replace_trip_resources

    trip = _reserved_trip(db, make_trip, students)
    trip.status = "in_progress"
    trip.actual_departure_time = trip.planned_departure_time
    db.commit()
    inc = create_trip_incident(db, trip_id=trip.id, reported_by_driver_id=None,
                               incident_type="vehicle_breakdown:engine",
                               description="x", occurred_at=datetime.now(timezone.utc))
    admin = db.query(User).filter_by(username="demo_admin").one()
    new_driver = db.query(Driver).filter(Driver.id != trip.driver_id, Driver.is_active.is_(True)).all()
    done = False
    for d in new_driver:
        try:
            replace_trip_resources(db, incident_id=inc.id, assigned_by_user_id=admin.id, driver_id=d.id)
            done = True
            break
        except Exception:
            db.rollback()
    assert done
    db.expire_all()
    assert db.query(Notification).filter_by(notification_type="trip_assigned_substitute").count() >= 1
