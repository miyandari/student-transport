# معماری پروژه هم‌مسیر

## 1. معرفی

سامانه «هم‌مسیر» یک سامانه چنددانشگاهی برای مدیریت سرویس ایاب‌وذهاب دانشجویان است.

معماری فعلی Backend بر پایه موارد زیر است:

- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic
- JWT Authentication
- WebSocket
- Service Layer
- API Router Layer

---

# 2. ساختار کلی پروژه

ساختار کلی Backend:

```text
app/
├── api/
├── core/
├── models/
├── schemas/
├── services/
├── realtime/
├── database.py
└── main.py
```

در کنار Backend:

```text
alembic/
docs/
requirements.txt
alembic.ini
```

مستندات وضعیت پروژه در:

```text
docs/project-context/
```

قرار دارند.

---

# 3. لایه API

پوشه:

```text
app/api/
```

مسئول دریافت درخواست‌های HTTP/WebSocket، کنترل دسترسی اولیه و فراخوانی Serviceها است.

اصل مهم:

> منطق اصلی کسب‌وکار نباید تا حد امکان داخل API Router نوشته شود.

API باید بیشتر وظایف زیر را انجام دهد:

- دریافت Request
- اعتبارسنجی اولیه
- دریافت Current User
- بررسی Role
- بررسی Scope
- فراخوانی Service
- تبدیل نتیجه به Response

---

# 4. لایه Service

پوشه:

```text
app/services/
```

محل اصلی منطق کسب‌وکار سامانه است.

Serviceهای مهم فعلی:

```text
reservation_service.py
boarding_request_service.py
trip_passenger_service.py
trip_lifecycle_service.py
vehicle_location_service.py
eta_service.py
station_event_service.py
trip_assignment_service.py
trip_incident_service.py
notification_service.py
student_penalty_service.py
report_service.py
```

همچنین Serviceهای دیگری برای بخش‌های مختلف سامانه وجود دارند.

---

# 5. Model Layer

پوشه:

```text
app/models/
```

مدل‌های اصلی پروژه شامل موارد زیر هستند:

```text
University
Student
User
Driver
TransportCompany
Contract
ContractDriver
ContractVehicle
Vehicle
VehicleLocation
Station
Route
RouteStation
Service
Schedule
Trip
TripAssignment
TripPassenger
TripIncident
Reservation
BoardingRequest
StationEvent
Feedback
AuditLog
Notification
```

ارتباط بین این مدل‌ها ساختار اصلی داده‌های سامانه را تشکیل می‌دهد.

---

# 6. University

University موجودیت اصلی محدوده دانشگاه است.

بسیاری از موجودیت‌های سامانه به دانشگاه وابسته‌اند.

در عملیات مدیریتی باید `university_id` بررسی شود تا کاربر دانشگاه به اطلاعات دانشگاه دیگری دسترسی نداشته باشد.

---

# 7. Student

Student اطلاعات دانشجو را نگهداری می‌کند.

اطلاعات مهم مرتبط با قوانین No-Show:

```text
no_show_count
negative_score
blocked_until
```

این اطلاعات توسط:

```text
student_penalty_service.py
```

مدیریت می‌شوند.

---

# 8. User و Authentication

User برای احراز هویت و نقش کاربر استفاده می‌شود.

Roleهای اصلی:

```text
super_admin
university_admin
transport_manager
company_admin
driver
student
```

Authentication بر پایه JWT انجام می‌شود.

در APIهای حساس باید علاوه بر Role، محدوده دسترسی نیز بررسی شود.

---

# 9. Transport Company

TransportCompany شرکت طرف قرارداد دانشگاه است.

شرکت می‌تواند دارای:

- راننده
- خودرو
- قرارداد
- سرویس
- Trip

باشد.

Company Admin فقط باید اطلاعات شرکت مجاز خود را مشاهده و مدیریت کند.

---

# 10. Contract

Contract ارتباط قراردادی بین دانشگاه و شرکت حمل‌ونقل را نگهداری می‌کند.

گزارش‌های مالی می‌توانند از اطلاعات قرارداد استفاده کنند.

---

# 11. Vehicle

Vehicle خودروهای مورد استفاده در سرویس را نگهداری می‌کند.

اطلاعات خودرو در Trip و Assignment استفاده می‌شود.

ظرفیت خودرو باید حداقل شامل:

- ظرفیت نشسته
- ظرفیت ایستاده

باشد.

---

# 12. Driver

Driver راننده سرویس است.

راننده می‌تواند به Trip یا Assignment مربوط شود.

راننده نباید بتواند اطلاعات سفرهایی را که به او مربوط نیستند مدیریت کند.

---

# 13. Route

Route مسیر سرویس است.

Route با RouteStation ارتباط دارد.

RouteStation ترتیب ایستگاه‌ها را مشخص می‌کند.

---

# 14. Station

Station ایستگاه سرویس است.

ایستگاه می‌تواند برای:

- Boarding
- Alighting
- ETA
- Station Event
- QR

استفاده شود.

---

# 15. Service

Service تعریف منطقی یک سرویس حمل‌ونقل است.

Service می‌تواند شامل:

- مسیر
- جنسیت مجاز
- ظرفیت
- برنامه زمانی

باشد.

---

# 16. Schedule

Schedule زمان‌بندی سرویس را مشخص می‌کند.

از Schedule می‌توان برای تولید یا مدیریت Trip استفاده کرد.

---

# 17. Trip

Trip یک اجرای مشخص از سرویس است.

چرخه کلی:

```text
Scheduled
    ↓
Boarding
    ↓
In Progress
    ↓
Completed
```

و در شرایط لازم:

```text
Cancelled
```

Trip موجودیت مرکزی بسیاری از عملیات است.

---

# 18. Trip Assignment

TripAssignment مشخص می‌کند در یک Trip چه راننده و خودرویی فعال هستند.

این بخش برای پشتیبانی از:

- راننده جایگزین
- خودرو جایگزین
- Incident
- تغییر Assignment

استفاده می‌شود.

در صورت وجود Assignment فعال، منطق موقعیت خودرو و عملیات راننده باید Assignment را مبنا قرار دهد.

---

# 19. Reservation

Reservation رزرو دانشجو برای Trip است.

Reservation باید:

- دانشجو را مشخص کند.
- Trip را مشخص کند.
- وضعیت رزرو را مشخص کند.
- از رزرو تکراری جلوگیری کند.

Reservation عادی می‌تواند به Boarding منجر شود.

Reservation لغوشده نباید No-Show محسوب شود.

---

# 20. Boarding Request

BoardingRequest برای درخواست سوارشدن استفاده می‌شود.

این موجودیت دو مسیر مهم دارد:

### درخواست عادی

درخواست دانشجو با:

```text
requires_driver_approval = false
```

در حالت ظرفیت مناسب می‌تواند خودکار تأیید شود.

### درخواست QR

درخواست QR بدون رزرو:

```text
requires_driver_approval = true
```

و نیازمند تأیید راننده است.

---

# 21. Trip Passenger

TripPassenger ثبت واقعی سوارشدن مسافر است.

اطلاعات آن می‌تواند شامل:

- دانشجو
- Trip
- Boarding Station
- Boarding Time
- Boarding Method
- وضعیت نشسته/ایستاده
- Alighting Time
- Alighting Station

باشد.

TripPassenger برای تشخیص No-Show نیز استفاده می‌شود.

---

# 22. Boarding Method

روش سوارشدن باید بتواند حالت‌های مختلف را تشخیص دهد.

از جمله:

```text
reservation
automatic_waitlist
boarding_without_reservation
```

نام دقیق مقدارها باید با پیاده‌سازی فعلی Service هماهنگ بماند.

---

# 23. Waitlist

Waitlist عمدتاً از طریق BoardingRequestهای pending عادی مدیریت می‌شود.

در صورت آزادشدن ظرفیت:

```text
TripPassenger
    ↓
Alight
    ↓
Waitlist Promotion
```

انجام می‌شود.

Promotion باید ظرفیت و جنسیت و وضعیت دانشجو را دوباره بررسی کند.

---

# 24. Vehicle Location

VehicleLocation موقعیت خودرو را ثبت می‌کند.

فرآیند اصلی:

```text
Driver
   ↓
Vehicle Location API
   ↓
Vehicle Location Service
   ↓
Database
   ↓
WebSocket
   ↓
Student / Management
```

---

# 25. WebSocket

WebSocket برای انتشار موقعیت لحظه‌ای خودرو استفاده می‌شود.

Endpoint اصلی:

```text
/ws/trips/{trip_id}/location
```

احراز هویت WebSocket با JWT انجام می‌شود.

دسترسی باید بر اساس:

- User
- Role
- University
- Company
- Trip
- Driver

کنترل شود.

---

# 26. ETA

ETA Service اطلاعات زیر را تحلیل می‌کند:

- آخرین موقعیت خودرو
- سرعت
- جهت حرکت
- فاصله تا ایستگاه
- پیشرفت مسیر

و وضعیت‌هایی مانند:

- GPS fresh
- GPS stale
- offline

را در نظر می‌گیرد.

سرعت‌های غیرواقعی نباید مستقیماً وارد محاسبات ETA شوند.

---

# 27. Station Event

StationEvent برای ثبت رویدادهای مرتبط با ایستگاه استفاده می‌شود.

از آن برای تشخیص مواردی مانند:

- نزدیک‌شدن
- رسیدن
- توقف
- عبور

استفاده می‌شود.

---

# 28. Notification

Notification برای اطلاع‌رسانی داخل سامانه استفاده می‌شود.

Notification می‌تواند به User مربوط باشد و در صورت نیاز Scope دانشگاه یا شرکت را نیز نگهداری کند.

Service اصلی:

```text
notification_service.py
```

است.

---

# 29. Student Penalty

منطق جریمه دانشجو در:

```text
student_penalty_service.py
```

قرار دارد.

این Service مسئول:

- محاسبه تعداد No-Show
- افزایش امتیاز منفی
- محاسبه مدت مسدودی
- بررسی فعال‌بودن مسدودی

است.

---

# 30. Trip Lifecycle

منطق چرخه عمر Trip در:

```text
trip_lifecycle_service.py
```

قرار دارد.

وظایف مهم:

- تکمیل Trip
- پردازش No-Show
- لغو Boarding Requestهای باقی‌مانده
- Notificationهای مرتبط
- بررسی استفاده کم از مسیر

است.

---

# 31. Trip Incident

TripIncident برای ثبت حوادث و مشکلات سفر است.

در صورت نیاز می‌تواند باعث ایجاد Assignment جایگزین شود.

Service مربوط:

```text
trip_incident_service.py
```

است.

---

# 32. Reports

گزارش‌ها در Service مربوط به:

```text
report_service.py
```

محاسبه می‌شوند.

گزارش‌های اصلی:

- Summary
- Financial
- Route Usage
- Driver Performance
- Vehicle Usage

هستند.

گزارش‌ها باید Scope دانشگاه/شرکت را رعایت کنند.

---

# 33. AuditLog

AuditLog برای ثبت عملیات حساس استفاده می‌شود.

یکی از کاربردهای مهم آن جلوگیری از ثبت دوباره جریمه No-Show است.

مثلاً:

```text
action = no_show_penalty
entity_type = reservation
entity_id = reservation.id
```

می‌تواند برای تشخیص جریمه قبلی استفاده شود.

---

# 34. Role-Based Access Control

کنترل دسترسی دو مرحله دارد:

### مرحله اول: Role

بررسی می‌شود کاربر چه نقشی دارد.

### مرحله دوم: Scope

بررسی می‌شود کاربر اجازه دسترسی به کدام:

- University
- Company
- Trip
- Vehicle
- Driver

را دارد.

بنابراین:

```text
Role + Scope
```

باید مبنای Authorization باشد.

---

# 35. Dependency Layer

بخشی از کنترل دسترسی در:

```text
app/core/dependencies.py
```

قرار دارد.

توابع مهم برای کنترل Scope در این لایه استفاده می‌شوند.

از جمله کنترل دسترسی دانشگاه، شرکت، Trip و Vehicle.

---

# 36. Realtime Layer

پوشه:

```text
app/realtime/
```

برای قابلیت‌های Real-Time استفاده می‌شود.

مهم‌ترین جزء:

```text
connection_manager
```

است که ارتباط WebSocket کاربران با Tripها را مدیریت می‌کند.

---

# 37. Database

Database اصلی:

```text
PostgreSQL
```

است.

SQLAlchemy ORM برای ارتباط با Database استفاده می‌شود.

Alembic برای Migration استفاده می‌شود.

---

# 38. Migration

Migrationها در:

```text
alembic/versions/
```

قرار دارند.

Migrationهای اخیر شامل:

```text
c1f48139cbb3
4d9a2c8f1b7e
4bc9e57efae5
3ffe513796d1
```

هستند.

در ایجاد Migration جدید باید ابتدا مشخص شود که تغییر واقعاً موردنیاز است.

---

# 39. جریان کلی Reservation تا Boarding

```text
Student
   ↓
Reservation / Boarding Request
   ↓
Validation
   ↓
Capacity Check
   ↓
┌─────────────────────┐
│ Capacity Available? │
└─────────┬───────────┘
          │
      Yes │ No
          │
          ↓
      Boarding      Waitlist
```

در QR:

```text
Student
   ↓
Scan QR
   ↓
Boarding Request
   ↓
Driver Approval
   ↓
Trip Passenger
```

---

# 40. جریان تکمیل Trip

```text
Trip reaches final station
        ↓
Validate final station
        ↓
Complete Trip
        ↓
Process No-Show
        ↓
Cancel remaining pending requests
        ↓
Notification
        ↓
Commit
```

---

# 41. اصل مهم معماری

Backend باید تا حد امکان دارای Separation of Concerns باشد:

```text
API
 ↓
Service
 ↓
Model / Database
```

و برای قابلیت‌های Real-Time:

```text
API / Service
 ↓
Realtime Layer
 ↓
WebSocket Clients
```

منطق کسب‌وکار نباید بدون دلیل در Routerها پراکنده شود.

---

# 42. اصل مهم توسعه

در ادامه توسعه:

- ابتدا فایل فعلی بررسی شود.
- تغییرات حداقلی و هدفمند باشند.
- Local مبنا قرار گیرد.
- نسخه قدیمی GitHub جایگزین Local نشود.
- هر فایل تغییرکرده کامل و یک‌جا ارائه شود.
- Migration بدون نیاز واقعی ایجاد نشود.
- تغییرات unrelated وارد Task جاری نشوند.

این فایل معماری مرجع پروژه است و در چت‌های بعدی برای درک ساختار کلی سامانه استفاده می‌شود.