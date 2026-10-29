# Project Context — هم‌مسیر

## اطلاعات اصلی

- نام پروژه: هم‌مسیر
- نوع پروژه: سامانه مدیریت سرویس ایاب‌وذهاب دانشجویی
- Repository: `miyandari/student-transport`
- Branch: `master`
- مسیر Local: `F:\project\student-transport`
- Backend: FastAPI
- Database: PostgreSQL 17.11
- Python: 3.13.9
- Virtual Environment: `.venv313`

---

## وضعیت فعلی

Backend عمدتاً تکمیل شده و در مرحله تثبیت و تست است.

نسخه Local از GitHub جلوتر است.

در حال حاضر نباید نسخه قدیمی GitHub جایگزین نسخه Local شود.

---

## قابلیت‌های اصلی تکمیل‌شده

- Authentication
- Role Based Access
- University
- Student
- Driver
- Transport Company
- Contract
- Vehicle
- Station
- Route
- Service
- Schedule
- Trip
- Trip Assignment
- Reservation
- Boarding Request
- Waitlist
- QR Boarding
- Trip Passenger
- Vehicle Location
- WebSocket
- ETA
- Station Event
- Notification
- No-Show
- Student Penalty
- Trip Incident
- Replacement Assignment
- Reports
- AuditLog

---

## قوانین کلیدی

### درخواست عادی

صندلی خالی:

```text
Automatic Approval → Boarding
```

صندلی پر ولی ظرفیت ایستاده موجود:

```text
Automatic Approval → Standing Boarding
```

تمام ظرفیت پر:

```text
Waitlist
```

درخواست عادی نیازمند تأیید راننده نیست.

---

## QR

QR بدون Reservation:

```text
Student
↓
Scan QR
↓
Boarding Request
↓
Driver Approval
↓
Boarding Without Reservation
```

QR تأییدشده نباید No-Show ایجاد کند.

---

## No-Show

در پایان Trip:

```text
Active Reservation
+
No Boarding
=
No-Show
```

هر No-Show:

```text
no_show_count += 1
negative_score += 1
```

مسدودی:

```text
1 → 0 days
2 → 1 day
3 → 3 days
4 → 5 days
5 → 7 days
6+ → 14 days
```

جریمه تکراری با AuditLog جلوگیری می‌شود.

لغو Reservation و Waitlist No-Show نیستند.

---

## ظرفیت

دو نوع ظرفیت:

- Seated
- Standing

ظرفیت باید در Reservation/Boarding/Waitlist/QR کنترل شود.

---

## جنسیت

دانشجو فقط می‌تواند از سرویس مجاز برای جنسیت خود استفاده کند.

این کنترل باید در تمام مسیرهای Boarding رعایت شود.

---

## نقش‌ها

```text
super_admin
university_admin
transport_manager
company_admin
driver
student
```

Authorization همیشه:

```text
Authentication
+
Role
+
Scope
```

است.

---

## Scope

Scopeهای مهم:

- University
- Transport Company
- Driver
- Vehicle
- Trip

University Admin نباید داده دانشگاه دیگر را ببیند.

Company Admin نباید داده شرکت دیگر را ببیند.

Driver نباید Trip یا Vehicle خارج از محدوده خود را مدیریت کند.

---

## فایل‌های مهم

```text
app/services/reservation_service.py
app/services/boarding_request_service.py
app/services/trip_passenger_service.py
app/services/trip_lifecycle_service.py
app/services/vehicle_location_service.py
app/services/eta_service.py
app/services/station_event_service.py
app/services/trip_assignment_service.py
app/services/trip_incident_service.py
app/services/notification_service.py
app/services/student_penalty_service.py
app/services/report_service.py
```

---

## فایل‌های Local-only یا جلوتر از GitHub

نمونه‌ها:

```text
app/models/notification.py
app/services/notification_service.py
app/services/student_penalty_service.py
app/services/boarding_request_service.py
app/services/report_service.py
```

این فهرست ممکن است پس از Commit/Push تغییر کند.

---

## Migrationهای مهم

```text
c1f48139cbb3
4d9a2c8f1b7e
4bc9e57efae5
3ffe513796d1
```

HEAD شناخته‌شده قبلی:

```text
7f3c2a91d6e4
```

---

## اجرای Backend

```powershell
cd F:\project\student-transport
uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## Git

قبل از ادامه توسعه، Commit محلی تغییرات فعلی:

```powershell
cd F:\project\student-transport
git status
git add .
git commit -m "Complete backend boarding, notification and trip lifecycle updates"
git status
git log -1 --oneline
```

Push فقط با درخواست صریح کاربر.

---

## مرحله فعلی

```text
Backend
↓
تکمیل قابلیت‌های اصلی
↓
تثبیت
↓
تست سناریوها
↓
بازبینی API / Service
↓
تکمیل Backend
↓
Frontend
↓
Student App
↓
Driver App
```

---

## سناریوهای مهم برای تست

1. Reservation با صندلی آزاد
2. Reservation با ظرفیت ایستاده
3. Waitlist
4. Promotion از Waitlist
5. QR بدون Reservation
6. QR با ظرفیت ایستاده
7. No-Show
8. جلوگیری از No-Show تکراری
9. مسدودی دانشجو
10. لغو Reservation
11. کنترل جنسیت
12. کنترل Scope
13. Trip Completion
14. Vehicle Location
15. WebSocket
16. ETA
17. Incident Replacement
18. Notification
19. Reports

---

## قواعد همکاری با کاربر

کاربر پروژه را شخصاً در سیستم Local توسعه می‌دهد.

هنگام تغییر فایل:

- کل فایل ارائه شود.
- فایل در یک Code Block باشد.
- کد به چند تکه تقسیم نشود.
- فایل بدون تغییر دوباره ارسال نشود.
- توضیحات کوتاه باشد.
- از تکرار مراحل قبلی خودداری شود.
- بدون درخواست کاربر Commit یا Push انجام نشود.

---

## دستور شروع در چت جدید

```text
پروژه «هم‌مسیر» را ادامه بده.
فایل docs/project-context/PROJECT_CONTEXT.md را بخوان.
سپس NEXT_STEPS.md را بررسی کن و از آخرین مرحله ادامه بده.
نسخه Local را مبنا قرار بده.
```

---

## اسناد کامل پروژه

برای جزئیات بیشتر:

```text
PROJECT_STATUS.md
NEXT_STEPS.md
BUSINESS_RULES.md
ARCHITECTURE.md
DEVELOPMENT_GUIDE.md
CHANGELOG.md
PROJECT_CONTEXT.md
```

این فایل خلاصه فشرده پروژه است و باید در شروع چت جدید اولین فایل مرجع باشد.