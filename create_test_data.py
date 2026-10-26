from datetime import time

from app.database import SessionLocal
from app.core.security import hash_password

from app.models.university import University
from app.models.user import User
from app.models.student import Student
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.models.station import Station
from app.models.route import Route
from app.models.route_station import RouteStation
from app.models.service import Service
from app.models.schedule import Schedule


db = SessionLocal()


def get_or_create(model, filters: dict, defaults: dict | None = None):
    obj = db.query(model).filter_by(**filters).first()

    if obj:
        return obj, False

    obj = model(
        **filters,
        **(defaults or {}),
    )

    db.add(obj)
    db.flush()

    return obj, True


try:
    # =====================================================
    # Universities
    # =====================================================

    university_a, _ = get_or_create(
        University,
        {"code": "TEST-A"},
        {
            "name": "دانشگاه تست آلفا",
            "is_active": True,
        },
    )

    university_b, _ = get_or_create(
        University,
        {"code": "TEST-B"},
        {
            "name": "دانشگاه تست بتا",
            "is_active": True,
        },
    )

    # =====================================================
    # Users
    # =====================================================

    admin_a, _ = get_or_create(
        User,
        {"username": "test_admin_a"},
        {
            "university_id": university_a.id,
            "first_name": "مدیر",
            "last_name": "آلفا",
            "phone": "09120000031",
            "password_hash": hash_password("Test@123456"),
            "role": "university_admin",
            "is_active": True,
        },
    )

    admin_b, _ = get_or_create(
        User,
        {"username": "test_admin_b"},
        {
            "university_id": university_b.id,
            "first_name": "مدیر",
            "last_name": "بتا",
            "phone": "09120000032",
            "password_hash": hash_password("Test@123456"),
            "role": "university_admin",
            "is_active": True,
        },
    )

    # =====================================================
    # Students
    # =====================================================

    student_a, _ = get_or_create(
        Student,
        {
            "university_id": university_a.id,
            "student_number": "TEST-A-001",
        },
        {
            "first_name": "دانشجوی",
            "last_name": "آلفا",
            "national_id": "9900000001",
            "phone": "09120000001",
            "is_active": True,
        },
    )

    student_b, _ = get_or_create(
        Student,
        {
            "university_id": university_b.id,
            "student_number": "TEST-B-001",
        },
        {
            "first_name": "دانشجوی",
            "last_name": "بتا",
            "national_id": "9900000002",
            "phone": "09120000002",
            "is_active": True,
        },
    )

    # =====================================================
    # Drivers
    # =====================================================

    driver_a, _ = get_or_create(
        Driver,
        {"license_number": "TEST-LICENSE-A"},
        {
            "university_id": university_a.id,
            "first_name": "راننده",
            "last_name": "آلفا",
            "national_id": "9800000001",
            "phone": "09120000011",
            "is_active": True,
        },
    )

    driver_b, _ = get_or_create(
        Driver,
        {"license_number": "TEST-LICENSE-B"},
        {
            "university_id": university_b.id,
            "first_name": "راننده",
            "last_name": "بتا",
            "national_id": "9800000002",
            "phone": "09120000012",
            "is_active": True,
        },
    )

    # =====================================================
    # Vehicles
    # =====================================================

    vehicle_a, _ = get_or_create(
        Vehicle,
        {"plate_number": "TEST-A-001"},
        {
            "university_id": university_a.id,
            "driver_id": driver_a.id,
            "vehicle_type": "bus",
            "capacity": 40,
            "is_active": True,
        },
    )

    vehicle_b, _ = get_or_create(
        Vehicle,
        {"plate_number": "TEST-B-001"},
        {
            "university_id": university_b.id,
            "driver_id": driver_b.id,
            "vehicle_type": "bus",
            "capacity": 40,
            "is_active": True,
        },
    )

    # =====================================================
    # Stations - University A
    # =====================================================

    station_a1, _ = get_or_create(
        Station,
        {
            "university_id": university_a.id,
            "name": "ایستگاه تست آلفا ۱",
        },
        {
            "address": "آدرس تست - ایستگاه ۱",
            "latitude": 35.7000,
            "longitude": 51.4000,
            "is_active": True,
        },
    )

    station_a2, _ = get_or_create(
        Station,
        {
            "university_id": university_a.id,
            "name": "ایستگاه تست آلفا ۲",
        },
        {
            "address": "آدرس تست - ایستگاه ۲",
            "latitude": 35.7050,
            "longitude": 51.4050,
            "is_active": True,
        },
    )

    station_a3, _ = get_or_create(
        Station,
        {
            "university_id": university_a.id,
            "name": "ایستگاه تست آلفا ۳",
        },
        {
            "address": "آدرس تست - ایستگاه ۳",
            "latitude": 35.7100,
            "longitude": 51.4100,
            "is_active": True,
        },
    )

    # =====================================================
    # Route - University A
    # =====================================================

    route_a, _ = get_or_create(
        Route,
        {
            "university_id": university_a.id,
            "code": "TEST-ROUTE-A",
        },
        {
            "name": "مسیر تست آلفا",
            "direction": "outbound",
            "description": "مسیر تست برای سرویس ایاب و ذهاب",
            "is_active": True,
        },
    )

    # =====================================================
    # Route Stations
    # =====================================================

    route_station_a1, _ = get_or_create(
        RouteStation,
        {
            "route_id": route_a.id,
            "station_id": station_a1.id,
        },
        {
            "stop_order": 1,
            "estimated_minutes_from_start": 0,
            "stop_duration_seconds": 30,
        },
    )

    route_station_a2, _ = get_or_create(
        RouteStation,
        {
            "route_id": route_a.id,
            "station_id": station_a2.id,
        },
        {
            "stop_order": 2,
            "estimated_minutes_from_start": 10,
            "stop_duration_seconds": 30,
        },
    )

    route_station_a3, _ = get_or_create(
        RouteStation,
        {
            "route_id": route_a.id,
            "station_id": station_a3.id,
        },
        {
            "stop_order": 3,
            "estimated_minutes_from_start": 20,
            "stop_duration_seconds": 30,
        },
    )

    # =====================================================
    # Service - University A
    # =====================================================

    service_a, _ = get_or_create(
        Service,
        {
            "university_id": university_a.id,
            "code": "TEST-SERVICE-A",
        },
        {
            "route_id": route_a.id,
            "name": "سرویس تست آلفا",
            "service_type": "regular",
            "is_active": True,
        },
    )

    # =====================================================
    # Schedule - University A
    # =====================================================

    schedule_a, _ = get_or_create(
        Schedule,
        {
            "university_id": university_a.id,
            "service_id": service_a.id,
            "day_of_week": 6,
            "departure_time": time(8, 0),
        },
        {
            "arrival_time": time(8, 30),
            "schedule_type": "regular",
            "is_active": True,
        },
    )

    db.commit()

    print()
    print("==============================================")
    print("Test data created successfully.")
    print("==============================================")
    print()
    print(f"University A ID : {university_a.id}")
    print(f"University B ID : {university_b.id}")
    print(f"Student A ID    : {student_a.id}")
    print(f"Student B ID    : {student_b.id}")
    print(f"Driver A ID     : {driver_a.id}")
    print(f"Driver B ID     : {driver_b.id}")
    print(f"Vehicle A ID    : {vehicle_a.id}")
    print(f"Vehicle B ID    : {vehicle_b.id}")
    print(f"Station A1 ID   : {station_a1.id}")
    print(f"Station A2 ID   : {station_a2.id}")
    print(f"Station A3 ID   : {station_a3.id}")
    print(f"Route A ID      : {route_a.id}")
    print(f"Service A ID    : {service_a.id}")
    print(f"Schedule A ID   : {schedule_a.id}")
    print()
    print("Admin A username: test_admin_a")
    print("Admin B username: test_admin_b")
    print("Test password   : Test@123456")
    print()

except Exception:
    db.rollback()
    raise

finally:
    db.close()