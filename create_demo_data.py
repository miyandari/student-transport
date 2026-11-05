"""
داده‌ی نمایشی (Demo) نزدیک به شرایط واقعی برای تست اپ دانشجو و راننده.

اجرا (از ریشه‌ی پروژه، با همان .env):
    python create_demo_data.py            # ساخت (اگر قبلاً ساخته شده، پاک و دوباره ساخته می‌شود)
    python create_demo_data.py --reset    # فقط پاک‌کردن داده‌ی نمایشی

فقط دانشگاه با کد DEMO-UT و وابسته‌هایش را پاک می‌کند؛ به داده‌ی دیگر دست نمی‌زند.
همه‌ی نام‌ها، کدملی‌ها و شماره‌ها ساختگی‌اند؛ مختصات ایستگاه‌ها تقریبی است.
"""

import random
import sys
from datetime import date, datetime, time, timedelta, timezone

from app.core.roles import Roles
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.boarding_request import BoardingRequest
from app.models.contract import Contract
from app.models.contract_driver import ContractDriver
from app.models.contract_vehicle import ContractVehicle
from app.models.driver import Driver
from app.models.feedback import Feedback
from app.models.notification import Notification
from app.models.reservation import Reservation
from app.models.route import Route
from app.models.route_station import RouteStation
from app.models.schedule import Schedule
from app.models.service import Service
from app.models.station import Station
from app.models.station_event import StationEvent
from app.models.student import Student
from app.models.transport_company import TransportCompany
from app.models.trip import Trip
from app.models.trip_assignment import TripAssignment
from app.models.trip_incident import TripIncident
from app.models.trip_passenger import TripPassenger
from app.models.university import University
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_location import VehicleLocation
from app.services.student_qr_service import generate_qr_token

UNI_CODE = "DEMO-UT"
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

STUDENT_PASSWORD = "Student@123"
DRIVER_PASSWORD = "Driver@123"
ADMIN_PASSWORD = "Admin@Demo123"

rng = random.Random(1405)

FEMALE_FIRST = [
    "زهرا", "فاطمه", "مریم", "سارا", "نگار", "الهام", "نرگس", "پریسا", "مهسا",
    "ندا", "الناز", "شقایق", "کیمیا", "آرزو", "نازنین", "هانیه", "ترانه",
    "یاسمن", "بهار", "ستاره", "مینا", "سمیرا", "فرزانه", "لیلا", "شیما",
    "تینا", "آتنا", "پگاه", "نیلوفر", "رویا",
]
MALE_FIRST = [
    "محمد", "علی", "حسین", "رضا", "امیرحسین", "مهدی", "سجاد", "امیر", "پوریا",
    "بهنام", "آرش", "کیان", "سینا", "پارسا", "مسعود", "حمید", "امین", "میلاد",
    "ایمان", "فرهاد", "کامران", "بابک", "ارسلان", "یاسین", "نیما", "دانیال",
    "سهیل", "مجتبی", "احسان", "محسن",
]
LAST = [
    "محمدی", "حسینی", "کریمی", "رضایی", "موسوی", "احمدی", "صادقی", "جعفری",
    "قاسمی", "نوری", "اکبری", "رحیمی", "فروغی", "کاظمی", "زارعی", "مرادی",
    "شریفی", "یزدانی", "عباسی", "اسدی", "طاهری", "سلطانی", "نجفی", "بابایی",
    "هاشمی", "ابراهیمی", "غفاری", "فلاحی", "پناهی", "سعیدی",
]
DRIVERS = [
    ("اکبر", "رحمانی"), ("جواد", "کرمانی"), ("حسن", "شاکری"),
    ("ناصر", "بهرامی"), ("داود", "خسروی"), ("منصور", "عطایی"),
    ("سعید", "امیری"), ("کریم", "توکلی"),
]

# (کلید، نام، آدرس، lat، lng)
# هشدار: مختصات همه‌ی ایستگاه‌ها «تقریبی و نمایشی» است (پراکنده در سطح شهر زنجان)،
# نه آدرس واقعی. برای دقت، مختصات واقعی را از نقشه جایگزین کنید.
# خوابگاه آوینی (دختران) داخل پردیس است و ایستگاه جدا و سرویس مستقل ندارد.
STATIONS = [
    ("campus", "پردیس دانشگاه علوم پزشکی", "زنجان، پردیس (شامل خوابگاه آوینی دختران)", 36.6860, 48.4740),
    ("med", "دانشکده پزشکی", "زنجان، دانشکده پزشکی", 36.6875, 48.4725),
    ("para", "دانشکده پیراپزشکی", "زنجان، دانشکده پیراپزشکی", 36.6840, 48.4760),
    ("h_valiasr", "بیمارستان ولیعصر", "بیمارستان آموزشی", 36.6805, 48.4905),
    ("h_mousavi", "بیمارستان موسوی", "بیمارستان آموزشی", 36.6735, 48.5010),
    # مکان‌های سرویس فوق‌العاده
    ("v_nouri", "سالن ورزشی نوری", "سالن ورزشی", 36.6905, 48.4690),
    ("v_taha", "مسجد طه", "مسجد", 36.6820, 48.4680),
    ("v_sadaf", "استخر صدف", "استخر", 36.6770, 48.4840),
    ("v_roozbeh", "سالن همایش‌های روزبه", "سالن همایش", 36.6850, 48.4860),
    # خوابگاه‌های پسران
    ("b_soleimani", "خوابگاه شهید سلیمانی", "خوابگاه پسران", 36.6990, 48.4560),
    ("b_andisheh", "خوابگاه اندیشه", "خوابگاه پسران", 36.7040, 48.4840),
    ("b_bahar", "خوابگاه بهار", "خوابگاه پسران", 36.6950, 48.5050),
    ("b_danesh", "خوابگاه دانش", "خوابگاه پسران", 36.6700, 48.5100),
    ("b_enghelab", "خوابگاه انقلاب", "خوابگاه پسران", 36.6760, 48.4930),
    ("b_pardis", "خوابگاه پردیس", "خوابگاه پسران", 36.6620, 48.4880),
    ("b_homa", "خوابگاه هما", "خوابگاه پسران", 36.6800, 48.4520),
    ("b_sina", "خوابگاه سینا", "خوابگاه پسران", 36.6720, 48.4640),
    # خوابگاه‌های دختران (به‌جز آوینی که داخل پردیس است)
    ("g_ferdows", "خوابگاه فردوس", "خوابگاه دختران", 36.6990, 48.4950),
    ("g_roozbeh", "خوابگاه روزبه", "خوابگاه دختران", 36.6840, 48.5000),
    ("g_shafa", "خوابگاه شفا", "خوابگاه دختران", 36.6650, 48.4780),
    ("g_farhang", "خوابگاه فرهنگ", "خوابگاه دختران", 36.6780, 48.4810),
    ("g_tohid", "خوابگاه توحید", "خوابگاه دختران", 36.6700, 48.4560),
    ("g_kosar", "خوابگاه کوثر", "خوابگاه دختران", 36.6890, 48.5120),
]

# (کد، نام، جهت، [ایستگاه‌ها])
ROUTES = [
    ("R1", "پسران: سلیمانی ← پردیس", "outbound",
     ["b_soleimani", "b_andisheh", "b_bahar", "campus"]),
    ("R2", "دختران: فردوس ← پردیس", "outbound",
     ["g_ferdows", "g_roozbeh", "g_shafa", "campus"]),
    ("R3", "پسران: دانش ← دانشکده پزشکی", "outbound",
     ["b_danesh", "b_enghelab", "b_pardis", "med"]),
    ("R4", "دختران: فرهنگ ← دانشکده پیراپزشکی", "outbound",
     ["g_farhang", "g_tohid", "g_kosar", "para"]),
    ("R5", "پردیس ← بیمارستان‌ها (مختلط)", "outbound",
     ["campus", "med", "para", "h_valiasr", "h_mousavi"]),
    ("R6", "پردیس ← بیمارستان‌ها (بانوان)", "outbound",
     ["campus", "h_valiasr", "h_mousavi"]),
    ("R7", "پسران: پردیس ← سینا", "inbound",
     ["campus", "b_homa", "b_sina"]),
    ("X1", "پردیس ← سالن ورزشی نوری", "outbound", ["campus", "v_nouri"]),
    ("X2", "پردیس ← مسجد طه", "outbound", ["campus", "v_taha"]),
    ("X3", "پردیس ← استخر صدف", "outbound", ["campus", "v_sadaf"]),
    ("X4", "پردیس ← سالن همایش‌های روزبه", "outbound",
     ["campus", "v_roozbeh"]),
]

# (کد، نام، مسیر، محدودیت جنسیتی، ساعت‌های حرکت، شاخص وسیله)
# سرویس‌های X «فوق‌العاده» هستند: برنامه‌ی ثابت ندارند و فقط سفر تک‌باره‌ی روزهای آینده دارند.
SERVICES = [
    ("S1", "", "R1", "male", [time(6, 45), time(12, 30)], 0),
    ("S2", "", "R2", "female", [time(6, 50), time(7, 40)], 1),
    ("S3", "", "R3", "male", [time(7, 0), time(7, 50)], 2),
    ("S4", "", "R4", "female", [time(7, 10), time(13, 0)], 3),
    ("S5", "", "R7", "male", [time(14, 0), time(16, 30)], 4),
    ("S6", "", "R6", "female", [time(8, 15), time(14, 30)], 5),
    ("S7", "", "R5", "mixed", [time(8, 0), time(13, 30)], 6),
    ("X1", "", "X1", "mixed", [], 7),
    ("X2", "", "X2", "mixed", [], 7),
    ("X3", "", "X3", "mixed", [], 4),
    ("X4", "", "X4", "mixed", [], 5),
]

# سفرهای فوق‌العاده: (کد سرویس، چند روز بعد، ساعت)
EXTRA_TRIPS = [
    ("X1", 1, time(17, 0)), ("X2", 1, time(11, 45)), ("X3", 2, time(16, 0)),
    ("X4", 2, time(9, 30)), ("X1", 3, time(18, 0)),
]

# (پلاک، نوع، ظرفیت نشسته، ظرفیت ایستاده)
VEHICLES = [
    ("12 ب 345 - 11", "bus", 40, 8),
    ("23 ج 678 - 22", "minibus", 12, 0),   # کوچک: برای دیدن لیست انتظار
    ("34 د 901 - 33", "bus", 38, 6),
    ("45 ص 234 - 44", "bus", 42, 8),
    ("56 ط 567 - 55", "minibus", 24, 0),
    ("67 س 890 - 66", "minibus", 24, 4),
    ("78 م 123 - 77", "bus", 40, 8),
    ("89 ل 456 - 88", "bus", 40, 8),
]


def utc(d: datetime) -> datetime:
    return d.astimezone(timezone.utc)


def at(day: date, t: time) -> datetime:
    """ساعت محلی ایران -> UTC."""
    return utc(datetime.combine(day, t, tzinfo=IRAN_TZ))


db = SessionLocal()


def reset(university_id: int, company_id: int | None) -> None:
    trip_ids = [
        r[0] for r in db.query(Trip.id).filter(Trip.university_id == university_id)
    ]
    user_ids = [
        r[0] for r in db.query(User.id).filter(User.university_id == university_id)
    ]
    if trip_ids:
        for model in (
            VehicleLocation, StationEvent, TripIncident, TripAssignment,
            BoardingRequest, TripPassenger, Feedback, Reservation,
        ):
            db.query(model).filter(model.trip_id.in_(trip_ids)).delete(
                synchronize_session=False
            )
    if user_ids:
        db.query(Notification).filter(Notification.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )
    uid = university_id
    db.query(Trip).filter(Trip.university_id == uid).delete()
    db.query(Schedule).filter(Schedule.university_id == uid).delete()
    db.query(Service).filter(Service.university_id == uid).delete()
    route_ids = [r[0] for r in db.query(Route.id).filter(Route.university_id == uid)]
    if route_ids:
        db.query(RouteStation).filter(RouteStation.route_id.in_(route_ids)).delete(
            synchronize_session=False
        )
    db.query(Route).filter(Route.university_id == uid).delete()
    db.query(Station).filter(Station.university_id == uid).delete()
    contract_ids = [
        r[0] for r in db.query(Contract.id).filter(Contract.university_id == uid)
    ]
    if contract_ids:
        db.query(ContractDriver).filter(
            ContractDriver.contract_id.in_(contract_ids)
        ).delete(synchronize_session=False)
        db.query(ContractVehicle).filter(
            ContractVehicle.contract_id.in_(contract_ids)
        ).delete(synchronize_session=False)
    db.query(Contract).filter(Contract.university_id == uid).delete()
    db.query(User).filter(User.university_id == uid).delete()
    db.query(Vehicle).filter(Vehicle.university_id == uid).delete()
    db.query(Driver).filter(Driver.university_id == uid).delete()
    db.query(Student).filter(Student.university_id == uid).delete()
    if company_id is not None:
        db.query(TransportCompany).filter(
            TransportCompany.id == company_id
        ).delete()
    db.query(University).filter(University.id == uid).delete()
    db.flush()


def main() -> None:
    only_reset = "--reset" in sys.argv

    existing = db.query(University).filter(University.code == UNI_CODE).first()
    if existing:
        company = (
            db.query(TransportCompany)
            .filter(TransportCompany.registration_number == "DEMO-CO-1")
            .first()
        )
        reset(existing.id, company.id if company else None)
        db.commit()
        print("داده‌ی نمایشی قبلی پاک شد.")
    if only_reset:
        return

    now = datetime.now(timezone.utc)
    today = datetime.now(IRAN_TZ).date()

    # ---------- دانشگاه، شرکت، قرارداد ----------
    uni = University(name="دانشگاه علوم پزشکی زنجان", code=UNI_CODE, is_active=True)
    db.add(uni)
    company = TransportCompany(
        name="شرکت حمل‌ونقل راه سبز",
        registration_number="DEMO-CO-1",
        phone="02155550000",
        address="زنجان، خیابان امام",
        is_active=True,
    )
    db.add(company)
    db.flush()

    contract = Contract(
        university_id=uni.id,
        transport_company_id=company.id,
        contract_number="DEMO-CT-1405",
        start_date=today - timedelta(days=200),
        end_date=today + timedelta(days=200),
        contract_amount=1_200_000_000,
        description="قرارداد ایاب‌وذهاب دانشجویی (نمایشی)",
        is_active=True,
    )
    db.add(contract)
    db.flush()

    # ---------- مدیران ----------
    admin_user = None
    for username, role, first, last, extra in [
        ("demo_admin", Roles.UNIVERSITY_ADMIN, "مهدی", "حکیمی", {}),
        ("demo_manager", Roles.TRANSPORT_MANAGER, "شهره", "انصاری", {}),
        ("demo_company", Roles.COMPANY_ADMIN, "کاوه", "صالحی",
         {"transport_company_id": company.id}),
    ]:
        u = User(
            username=username, password_hash=hash_password(ADMIN_PASSWORD),
            first_name=first, last_name=last, role=role,
            university_id=uni.id, is_active=True, **extra,
        )
        db.add(u)
        admin_user = admin_user or u
    db.flush()

    # ---------- راننده و خودرو ----------
    drivers: list[Driver] = []
    vehicles: list[Vehicle] = []
    for i, (first, last) in enumerate(DRIVERS):
        d = Driver(
            university_id=uni.id, transport_company_id=company.id,
            first_name=first, last_name=last,
            national_id=f"05{rng.randrange(10**7, 10**8)}",
            phone=f"0912{rng.randrange(1000000, 9999999)}",
            license_number=f"DEMO-LIC-{i + 1:03d}", is_active=True,
        )
        db.add(d)
        drivers.append(d)
    db.flush()
    for i, (plate, vtype, seated, standing) in enumerate(VEHICLES):
        v = Vehicle(
            university_id=uni.id, transport_company_id=company.id,
            driver_id=drivers[i].id, plate_number=plate, vehicle_type=vtype,
            capacity=seated + standing, is_active=True,
        )
        db.add(v)
        vehicles.append(v)
    db.flush()
    for i, d in enumerate(drivers):
        db.add(User(
            username=f"driver{i + 1}", password_hash=hash_password(DRIVER_PASSWORD),
            first_name=d.first_name, last_name=d.last_name, phone=d.phone,
            role=Roles.DRIVER, university_id=uni.id,
            transport_company_id=company.id, driver_id=d.id, is_active=True,
        ))
        db.add(ContractDriver(
            contract_id=contract.id, driver_id=d.id,
            start_date=contract.start_date, end_date=contract.end_date,
            is_active=True,
        ))
        db.add(ContractVehicle(
            contract_id=contract.id, vehicle_id=vehicles[i].id,
            start_date=contract.start_date, end_date=contract.end_date,
            is_active=True,
        ))

    # ---------- ایستگاه، مسیر ----------
    stations: dict[str, Station] = {}
    for key, name, address, lat, lng in STATIONS:
        s = Station(
            university_id=uni.id, name=name, address=address,
            latitude=lat, longitude=lng, is_active=True,
        )
        db.add(s)
        stations[key] = s
    db.flush()

    routes: dict[str, Route] = {}
    route_stops: dict[str, list[Station]] = {}
    for code, name, direction, keys in ROUTES:
        name = f"{stations[keys[0]].name} ← {stations[keys[-1]].name}"
        r = Route(
            university_id=uni.id, name=name, code=f"DEMO-{code}",
            direction=direction, description=name, is_active=True,
        )
        db.add(r)
        db.flush()
        routes[code] = r
        route_stops[code] = [stations[k] for k in keys]
        for order, k in enumerate(keys, start=1):
            db.add(RouteStation(
                route_id=r.id, station_id=stations[k].id, stop_order=order,
                estimated_minutes_from_start=(order - 1) * 8,
                stop_duration_seconds=30,
            ))
    db.flush()

    # ---------- سرویس و برنامه ----------
    services: dict[str, Service] = {}
    schedules: dict[str, list[Schedule]] = {}
    for code, name, rcode, gender, times, _ in SERVICES:
        ends = route_stops[rcode]
        extra = code.startswith("X")
        name = (
            f"سرویس فوق‌العاده از {ends[0].name} به {ends[-1].name}"
            if extra
            else f"سرویس از {ends[0].name} به {ends[-1].name}"
        )
        if gender == "female":
            name += " (ویژه بانوان)"
        elif gender == "male":
            name += " (ویژه آقایان)"
        sv = Service(
            university_id=uni.id, route_id=routes[rcode].id,
            contract_id=contract.id, name=name, code=f"DEMO-{code}",
            service_type="extra" if extra else "regular",
            gender_restriction=gender, is_active=True,
        )
        db.add(sv)
        db.flush()
        services[code] = sv
        schedules[code] = []
        for t in times:
            arrival = (datetime.combine(today, t) + timedelta(minutes=40)).time()
            for dow in range(0, 6):  # شنبه تا پنج‌شنبه
                sc = Schedule(
                    university_id=uni.id, service_id=sv.id, day_of_week=dow,
                    departure_time=t, arrival_time=arrival,
                    schedule_type="regular", is_active=True,
                )
                db.add(sc)
                schedules[code].append(sc)
    db.flush()

    # ---------- دانشجوها ----------
    students: list[Student] = []
    used_numbers: set[str] = set()
    for gender, firsts in (("female", FEMALE_FIRST), ("male", MALE_FIRST)):
        for first in firsts:
            while True:
                number = f"4021{rng.randrange(10000, 99999)}"
                if number not in used_numbers:
                    used_numbers.add(number)
                    break
            st = Student(
                university_id=uni.id, student_number=number, first_name=first,
                last_name=rng.choice(LAST), gender=gender,
                national_id=f"00{rng.randrange(10**7, 10**8)}",
                phone=f"0935{rng.randrange(1000000, 9999999)}",
                qr_token=generate_qr_token(), is_active=True,
                no_show_count=0, negative_score=0,
            )
            db.add(st)
            students.append(st)
    db.flush()
    for st in students:
        db.add(User(
            username=st.student_number,
            password_hash=hash_password(STUDENT_PASSWORD),
            first_name=st.first_name, last_name=st.last_name, phone=st.phone,
            role=Roles.STUDENT, university_id=uni.id, student_id=st.id,
            is_active=True,
        ))
    db.flush()

    hero_f = next(s for s in students if s.gender == "female")
    hero_m = next(s for s in students if s.gender == "male")
    heroes = {hero_f.id, hero_m.id}
    pool = [s for s in students if s.id not in heroes]

    # وضعیت‌های خاص: غیبت/امتیاز منفی/مسدود
    rest = pool[:]
    rng.shuffle(rest)
    for st in rest[:5]:
        st.no_show_count = rng.randint(1, 2)
        st.negative_score = st.no_show_count * 2
    for st in rest[5:7]:
        st.no_show_count = 3
        st.negative_score = 6
        st.blocked_until = now + timedelta(days=rng.randint(1, 4))
    blocked_ids = {s.id for s in rest[5:7]}
    eligible = [s for s in pool if s.id not in blocked_ids]

    # ---------- سفرها ----------
    trips: list[tuple[Trip, str, list[Station]]] = []

    def make_trip(code, day, dep, status, vehicle_idx, schedule=None,
                  actual_dep=None, actual_arr=None):
        v = vehicles[vehicle_idx]
        seated, standing = VEHICLES[vehicle_idx][2], VEHICLES[vehicle_idx][3]
        t = Trip(
            university_id=uni.id, service_id=services[code].id,
            schedule_id=schedule.id if schedule else None,
            driver_id=drivers[vehicle_idx].id, vehicle_id=v.id,
            seated_capacity=seated, standing_capacity=standing or None,
            allow_standing=standing > 0, trip_date=day,
            planned_departure_time=dep, actual_departure_time=actual_dep,
            actual_arrival_time=actual_arr, status=status, is_active=True,
        )
        db.add(t)
        db.flush()
        db.add(TripAssignment(
            trip_id=t.id, driver_id=t.driver_id, vehicle_id=t.vehicle_id,
            assigned_by_user_id=admin_user.id,
            assignment_type="primary", start_at=dep, is_active=True,
        ))
        route_code = next(s[2] for s in SERVICES if s[0] == code)
        trips.append((t, code, route_stops[route_code]))
        return t

    for offset in range(-1, 4):  # دیروز تا سه روز بعد
        day = today + timedelta(days=offset)
        dow = (day.weekday() + 2) % 7
        if dow == 6:
            continue  # جمعه
        for code, _n, _r, _g, _times, vidx in SERVICES:
            for sc in [s for s in schedules[code] if s.day_of_week == dow]:
                dep = at(day, sc.departure_time)
                end = dep + timedelta(minutes=40)
                if end <= now:
                    make_trip(code, day, dep, "completed", vidx, sc,
                              dep + timedelta(minutes=rng.randint(0, 4)),
                              end + timedelta(minutes=rng.randint(0, 6)))
                elif dep <= now:
                    make_trip(code, day, dep, "in_progress", vidx, sc,
                              dep + timedelta(minutes=1))
                else:
                    make_trip(code, day, dep, "scheduled", vidx, sc)

    # سفرهای فوق‌العاده‌ی آینده (بدون برنامه‌ی ثابت)
    for code, ahead, t in EXTRA_TRIPS:
        vidx = next(x[5] for x in SERVICES if x[0] == code)
        day = today + timedelta(days=ahead)
        make_trip(code, day, at(day, t), "scheduled", vidx)

    # سفرهای «همین الان»: برای دیدن نقشه‌ی زنده و صفحه‌ی سوارشدن، مستقل از ساعت اجرا
    live = make_trip("S1", today, now - timedelta(minutes=14), "in_progress", 6,
                     None, now - timedelta(minutes=12))
    make_trip("S7", today, now + timedelta(minutes=7), "boarding", 7)
    make_trip("S3", today, now + timedelta(minutes=45), "scheduled", 2)
    make_trip("S2", today, now + timedelta(minutes=70), "scheduled", 1)

    # موقعیت زنده‌ی خودرو روی مسیر S1 (بین ایستگاه دوم و سوم)
    stops = route_stops["R1"]
    a, b = stops[1], stops[2]  # بین اندیشه و بهار
    for i in range(24):
        f = i / 23
        db.add(VehicleLocation(
            trip_id=live.id, vehicle_id=live.vehicle_id,
            latitude=a.latitude + (b.latitude - a.latitude) * f,
            longitude=a.longitude + (b.longitude - a.longitude) * f,
            speed=rng.uniform(20, 45), heading=170.0,
            recorded_at=now - timedelta(seconds=(23 - i) * 20 + 5),
        ))
    db.flush()

    # ---------- رزرو، سوارشدن، بازخورد ----------
    def allowed(trip_code: str, st: Student) -> bool:
        g = services[trip_code].gender_restriction
        return g == "mixed" or g == st.gender

    busy_day: set[tuple[int, date]] = set()
    stats = {"reservations": 0, "waitlisted": 0, "cancelled": 0,
             "passengers": 0, "feedbacks": 0}

    def reserve(trip, st, stops, status="active", standing=False):
        busy_day.add((st.id, trip.trip_date))
        res = Reservation(
            trip_id=trip.id, student_id=st.id,
            station_id=rng.choice(stops).id, reservation_time=now - timedelta(
                hours=rng.randint(1, 30)),
            status=status, is_standing=standing,
        )
        db.add(res)
        stats["reservations"] += 1
        if status == "waitlisted":
            stats["waitlisted"] += 1
        if status == "cancelled":
            stats["cancelled"] += 1
        return res

    rating_text = {
        5: "عالی بود", 4: "خوب بود، کمی تأخیر داشت", 3: "معمولی",
        2: "راننده تند رانندگی می‌کرد", 1: "خودرو تمیز نبود",
    }

    # سرویس کوچک بانوان اول پردازش می‌شود تا بانوان کافی برای پر شدن و لیست انتظار باشند
    ordered = sorted(
        trips,
        key=lambda x: (x[0].schedule_id is not None, x[1] != 'S2', x[0].id),
    )
    for trip, code, stops_ in ordered:
        cap = trip.seated_capacity or 0
        candidates = [s for s in eligible if allowed(code, s)
                      and (s.id, trip.trip_date) not in busy_day]
        rng.shuffle(candidates)

        if trip.status == "completed":
            n = min(len(candidates), max(3, int(cap * rng.uniform(0.4, 0.9))))
            for st in candidates[:n]:
                res = reserve(trip, st, stops_)
                if rng.random() < 0.9:
                    board = trip.actual_departure_time
                    db.add(TripPassenger(
                        trip_id=trip.id, student_id=st.id,
                        boarding_time=board, boarding_station_id=res.station_id,
                        alighting_time=trip.actual_arrival_time,
                        alighting_station_id=stops_[-1].id,
                        boarding_method=rng.choice(["qr", "qr", "manual", "driver"]),
                        is_standing=False,
                    ))
                    stats["passengers"] += 1
                    if rng.random() < 0.45:
                        rating = rng.choices([5, 4, 3, 2, 1], [40, 30, 15, 10, 5])[0]
                        db.add(Feedback(
                            trip_id=trip.id, student_id=st.id, rating=rating,
                            feedback_type="trip_rating", title="امتیاز سفر",
                            message=rating_text[rating],
                            created_at=trip.actual_arrival_time,
                            is_resolved=False,
                        ))
                        stats["feedbacks"] += 1
        else:
            # سرویس بانوان کوچک (S2) را پر می‌کنیم تا لیست انتظار دیده شود
            fill = 1.15 if code == "S2" else rng.uniform(0.15, 0.85)
            n = min(len(candidates), int(cap * fill))
            if trip.status in ("in_progress", "boarding"):
                n = max(n, min(len(candidates), 8))  # راننده لیست مسافر داشته باشد
            made = []
            for i, st in enumerate(candidates[:n]):
                if i < cap:
                    made.append((st, reserve(trip, st, stops_)))
                else:
                    reserve(trip, st, stops_, "waitlisted")
            if trip.status in ("in_progress", "boarding"):
                # حدود ۶۰٪ سوار شده‌اند؛ برای سفر در حال سوارکردن چند درخواست QR هم معلق است.
                cut = int(len(made) * 0.6)
                for st, res in made[:cut]:
                    db.add(TripPassenger(
                        trip_id=trip.id, student_id=st.id,
                        boarding_time=now - timedelta(minutes=rng.randint(1, 10)),
                        boarding_station_id=res.station_id,
                        boarding_method="qr", is_standing=False,
                    ))
                if trip.status == "boarding":
                    for st, res in made[cut:cut + 2]:
                        db.add(BoardingRequest(
                            trip_id=trip.id, student_id=st.id,
                            boarding_station_id=res.station_id,
                            is_standing=False, requires_driver_approval=True,
                            status="pending",
                            requested_at=now - timedelta(minutes=1),
                        ))
            for st in candidates[n:n + 2]:
                if trip.status == "scheduled":
                    reserve(trip, st, stops_, "cancelled")

    # ---------- سناریوهای مشخص برای دو دانشجوی نمایشی ----------
    def stops_of(trip_code):
        return next(t[2] for t in trips if t[1] == trip_code)

    def first_trip(code, *statuses):
        for t, c, _s in trips:
            if c == code and t.status in statuses:
                return t
        return None

    for hero, code_open, code_done in (
        (hero_f, "S6", "S2"), (hero_m, "S5", "S3"),
    ):
        done = [t for t, c, _s in trips if c == code_done
                and t.status == "completed"]
        upcoming = [t for t, c, _s in trips if c == code_open
                    and t.status == "scheduled"]
        other = [t for t, c, _s in trips if c in ("S1", "S4")
                 and t.status == "scheduled" and t.id != (live.id if live else 0)]
        # 1) سفر انجام‌شده بدون امتیاز، 2) انجام‌شده با امتیاز
        for i, t in enumerate(done[:2]):
            if (hero.id, t.trip_date) in busy_day:
                continue
            res = reserve(t, hero, stops_of(code_done))
            db.add(TripPassenger(
                trip_id=t.id, student_id=hero.id,
                boarding_time=t.actual_departure_time,
                boarding_station_id=res.station_id,
                alighting_time=t.actual_arrival_time,
                alighting_station_id=stops_of(code_done)[-1].id,
                boarding_method="qr", is_standing=False,
            ))
            if i == 1:
                db.add(Feedback(
                    trip_id=t.id, student_id=hero.id, rating=5,
                    feedback_type="trip_rating", title="امتیاز سفر",
                    message="راننده خوش‌برخورد بود", is_resolved=False,
                    created_at=t.actual_arrival_time,
                ))
        # 3) رزرو فعال، 4) لغوشده (برای رزرو مجدد)، 5) لیست انتظار
        picks = [t for t in upcoming + other if (hero.id, t.trip_date) not in busy_day]
        codes = {t.id: next(c for tt, c, _s in trips if tt.id == t.id) for t in picks}
        for status, t in zip(("active", "cancelled", "waitlisted"), picks):
            if status == "waitlisted":
                continue
            reserve(t, hero, stops_of(codes[t.id]), status)

    # بانوی نمایشی: یک رزرو در لیست انتظار هم داشته باشد
    for t, c, st_ in trips:
        if (c == "S2" and t.status == "scheduled"
                and (hero_f.id, t.trip_date) not in busy_day
                and db.query(Reservation).filter(
                    Reservation.trip_id == t.id,
                    Reservation.status == "waitlisted").count() > 0):
            reserve(t, hero_f, st_, "waitlisted")
            break

    # ---------- اعلان‌ها ----------
    samples = [
        ("reservation", "رزرو ثبت شد", "رزرو شما برای سفر فردا ثبت شد."),
        ("trip", "یادآوری سفر", "سفر شما ۳۰ دقیقه دیگر حرکت می‌کند."),
        ("trip", "تأخیر در سرویس", "سرویس به‌دلیل ترافیک حدود ۱۰ دقیقه تأخیر دارد."),
        ("system", "به هم‌مسیر خوش آمدید", "از اینجا می‌توانید سفرها را رزرو کنید."),
        ("reservation", "رزرو لغو شد", "رزرو شما لغو شد."),
        ("reservation", "از لیست انتظار خارج شدید", "برای سفر شما جای خالی شد."),
    ]
    user_by_student = {
        u.student_id: u
        for u in db.query(User).filter(User.university_id == uni.id,
                                       User.student_id.isnot(None))
    }
    notif_count = 0
    for st in students:
        user = user_by_student[st.id]
        n = 6 if st.id in heroes else rng.randint(1, 4)
        for i, (ntype, title, message) in enumerate(rng.sample(samples, n)):
            db.add(Notification(
                user_id=user.id, university_id=uni.id, notification_type=ntype,
                title=title, message=message, data={},
                is_read=i >= 2 and rng.random() < 0.6,
                created_at=now - timedelta(hours=3 * (i + 1) + rng.randint(0, 2)),
            ))
            notif_count += 1

    db.commit()

    by_status = {}
    for t, _c, _s in trips:
        by_status[t.status] = by_status.get(t.status, 0) + 1

    print()
    print("=" * 56)
    print("داده‌ی نمایشی ساخته شد")
    print("=" * 56)
    print(f"دانشجو: {len(students)} | راننده: {len(drivers)} | خودرو: {len(vehicles)}")
    print(f"ایستگاه: {len(stations)} | مسیر: {len(routes)} | سرویس: {len(services)}")
    print(f"سفر: {len(trips)} {by_status}")
    print(f"رزرو: {stats['reservations']} (لیست انتظار {stats['waitlisted']}، "
          f"لغو {stats['cancelled']}) | سوارشده: {stats['passengers']} "
          f"| بازخورد: {stats['feedbacks']} | اعلان: {notif_count}")
    print()
    print("ورود دانشجو (رمز همه: " + STUDENT_PASSWORD + ")")
    print(f"  بانو  : {hero_f.student_number}  ({hero_f.first_name} {hero_f.last_name})")
    print(f"  آقا   : {hero_m.student_number}  ({hero_m.first_name} {hero_m.last_name})")
    blocked = [s for s in students if s.id in blocked_ids]
    for s in blocked:
        print(f"  مسدود : {s.student_number}  ({s.first_name} {s.last_name})")
    print(f"راننده: driver1 ... driver{len(drivers)}  رمز: {DRIVER_PASSWORD}")
    print(f"مدیر: demo_admin / demo_manager / demo_company  رمز: {ADMIN_PASSWORD}")
    print()


try:
    main()
except Exception:
    db.rollback()
    raise
finally:
    db.close()
