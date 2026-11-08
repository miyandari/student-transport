from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.services import reservation_service as rs
from app.services import trip_passenger_service as tps


def _pool(trip, students):
    r = (trip.service.gender_restriction or "mixed").lower()
    return [s for s in students if r == "mixed" or s.gender == r]


def test_reservation_always_seated_and_full_message(db, make_trip, students):
    trip = make_trip(seated=1, standing=5, status="scheduled")
    a, b = _pool(trip, students)[:2]
    r = rs.create_reservation(db, trip_id=trip.id, student_id=a.id, is_standing=True)
    assert r.is_standing is False and r.status == "active"
    with pytest.raises(HTTPException) as e:
        rs.create_reservation(db, trip_id=trip.id, student_id=b.id)
    assert e.value.status_code == 409
    assert "تأیید راننده" in e.value.detail


def test_reserved_student_gets_seat_and_walkin_cannot_take_it(db, make_trip, students):
    trip = make_trip(seated=1, standing=2, status="scheduled")
    a, b = _pool(trip, students)[:2]
    rs.create_reservation(db, trip_id=trip.id, student_id=a.id)
    trip.status = "boarding"
    db.commit()
    # مسافر بدون رزرو نمی‌تواند صندلی رزروشده را بگیرد
    with pytest.raises(HTTPException):
        tps.board_passenger(db, trip_id=trip.id, student_id=b.id, boarding_method="qr",
                            is_standing=False, boarding_station_id=None)
    # دارای رزرو حتی با درخواست ایستاده روی صندلی می‌نشیند
    p = tps.board_passenger(db, trip_id=trip.id, student_id=a.id, boarding_method="qr",
                            is_standing=True, boarding_station_id=None)
    assert p.is_standing is False


def test_unknown_capacity_with_driver_acts_as_full(db, make_trip, students):
    trip = make_trip(seated=1, status="scheduled")
    trip.seated_capacity = None
    db.commit()
    a = _pool(trip, students)[0]
    with pytest.raises(HTTPException) as e:
        rs.create_reservation(db, trip_id=trip.id, student_id=a.id)
    assert e.value.status_code == 409
    assert "تأیید راننده" in e.value.detail


def test_no_driver_cannot_reserve(db, make_trip, students):
    trip = make_trip(seated=3, status="scheduled")
    trip.driver_id = None
    db.commit()
    a = _pool(trip, students)[0]
    with pytest.raises(HTTPException) as e:
        rs.create_reservation(db, trip_id=trip.id, student_id=a.id)
    assert e.value.status_code == 400
    assert "راننده" in e.value.detail
