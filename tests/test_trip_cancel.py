from datetime import datetime, timezone

from app.models.boarding_request import BoardingRequest
from app.models.reservation import Reservation
from app.services import boarding_request_service as brs
from app.services.trip_service import update_trip_status


def test_cancel_trip_cancels_reservations_and_pending_requests(db, make_trip, students):
    trip = make_trip(seated=5, status="scheduled")
    r = (trip.service.gender_restriction or "mixed").lower()
    pool = [s for s in students if r == "mixed" or s.gender == r]
    a, b = pool[0], pool[1]
    db.add(Reservation(trip_id=trip.id, student_id=a.id, status="active", is_standing=False,
                       reservation_time=datetime.now(timezone.utc)))
    db.commit()
    trip.status = "boarding"
    db.commit()
    req = brs.create_boarding_request(db, student_id=b.id, trip_id=trip.id, requires_driver_approval=True)

    update_trip_status(db, trip, "cancelled")

    db.expire_all()
    assert db.query(Reservation).filter_by(trip_id=trip.id, status="active").count() == 0
    assert db.get(BoardingRequest, req.id).status == "cancelled"
