import pytest
from fastapi import HTTPException

from app.models.boarding_request import BoardingRequest
from app.models.trip_passenger import TripPassenger
from app.services import boarding_request_service as brs
from app.services import trip_passenger_service as tps


def _eligible(db, trip, students, n):
    """n دانشجوی مجاز برای سرویس سفر (با رعایت جنسیت)."""
    r = (trip.service.gender_restriction or "mixed").lower()
    out = [s for s in students if r == "mixed" or s.gender == r]
    assert len(out) >= n, "داده‌ی دمو کافی نیست"
    return out[:n]


def _board(db, trip, st, standing=False):
    return tps.board_passenger(
        db, trip_id=trip.id, student_id=st.id, boarding_method="qr",
        is_standing=standing, boarding_station_id=None,
    )


def test_seated_capacity_enforced(db, make_trip, students):
    trip = make_trip(seated=2, standing=0)
    a, b, c = _eligible(db, trip, students, 3)
    _board(db, trip, a)
    _board(db, trip, b)
    with pytest.raises(HTTPException) as e:
        _board(db, trip, c)
    assert e.value.status_code in (400, 409)
    assert db.query(TripPassenger).filter_by(trip_id=trip.id).count() == 2


def test_standing_capacity_enforced(db, make_trip, students):
    trip = make_trip(seated=1, standing=1)
    a, b, c = _eligible(db, trip, students, 3)
    _board(db, trip, a)
    _board(db, trip, b, standing=True)
    with pytest.raises(HTTPException):
        _board(db, trip, c, standing=True)
    assert db.query(TripPassenger).filter_by(trip_id=trip.id).count() == 2


def test_duplicate_boarding_rejected(db, make_trip, students):
    trip = make_trip(seated=3)
    (a,) = _eligible(db, trip, students, 1)
    _board(db, trip, a)
    with pytest.raises(HTTPException) as e:
        _board(db, trip, a)
    assert e.value.status_code in (400, 409)
    assert db.query(TripPassenger).filter_by(trip_id=trip.id, student_id=a.id).count() == 1


def test_pending_qr_request_is_idempotent(db, make_trip, students):
    trip = make_trip(seated=3)
    (a,) = _eligible(db, trip, students, 1)
    r1 = brs.create_boarding_request(db, student_id=a.id, trip_id=trip.id, requires_driver_approval=True)
    r2 = brs.create_boarding_request(db, student_id=a.id, trip_id=trip.id, requires_driver_approval=True)
    assert r1.id == r2.id
    assert db.query(BoardingRequest).filter_by(trip_id=trip.id, student_id=a.id).count() == 1


def test_approve_boards_atomically_and_blocks_double_decision(db, make_trip, students):
    trip = make_trip(seated=3)
    (a,) = _eligible(db, trip, students, 1)
    r = brs.create_boarding_request(db, student_id=a.id, trip_id=trip.id, requires_driver_approval=True)
    out = brs.approve_boarding_request(db, request_id=r.id, responded_by_user_id=1)
    assert out.status == "approved"
    assert db.query(TripPassenger).filter_by(trip_id=trip.id, student_id=a.id).count() == 1
    with pytest.raises(HTTPException):
        brs.approve_boarding_request(db, request_id=r.id, responded_by_user_id=1)
    with pytest.raises(HTTPException):
        brs.reject_boarding_request(db, request_id=r.id, responded_by_user_id=1)


def test_approve_when_full_leaves_request_pending(db, make_trip, students):
    trip = make_trip(seated=1)
    a, b = _eligible(db, trip, students, 2)
    _board(db, trip, a)
    r = brs.create_boarding_request(db, student_id=b.id, trip_id=trip.id, requires_driver_approval=True)
    with pytest.raises(HTTPException):
        brs.approve_boarding_request(db, request_id=r.id, responded_by_user_id=1)
    db.rollback()
    db.expire_all()
    assert db.get(BoardingRequest, r.id).status == "pending"
    assert db.query(TripPassenger).filter_by(trip_id=trip.id).count() == 1


def test_automatic_request_waitlists_when_full(db, make_trip, students):
    trip = make_trip(seated=1)
    a, b = _eligible(db, trip, students, 2)
    r1 = brs.create_boarding_request(db, student_id=a.id, trip_id=trip.id)
    assert r1.status == "approved"
    r2 = brs.create_boarding_request(db, student_id=b.id, trip_id=trip.id)
    assert r2.status != "approved"
    assert db.query(TripPassenger).filter_by(trip_id=trip.id).count() == 1
