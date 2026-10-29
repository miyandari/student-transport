# راهنمای توسعه پروژه هم‌مسیر

## 1. مشخصات پروژه

**نام:** هم‌مسیر  
**نوع:** سامانه مدیریت سرویس ایاب‌وذهاب دانشجویی  
**Repository:** `miyandari/student-transport`  
**Branch:** `master`

مسیر پروژه در سیستم محلی:

```text
F:\project\student-transport
```

---

# 2. محیط توسعه

## Python

نسخه مورد استفاده:

```text
Python 3.13.9
```

محیط مجازی:

```text
.venv313
```

نسخه Python 3.15 قبلاً برای پروژه استفاده شده بود، اما به‌دلیل مشکلات نصب و دانلود وابستگی‌ها، محیط پروژه به Python 3.13.9 منتقل شد.

بنابراین در ادامه توسعه از Python 3.13.9 استفاده شود.

---

# 3. PostgreSQL

نسخه PostgreSQL:

```text
17.11
```

Database پروژه PostgreSQL است.

مدیریت Database در صورت نیاز با pgAdmin انجام می‌شود.

pgAdmin در محیط فعلی روی:

```text
127.0.0.1:8580
```

در دسترس بوده است.

---

# 4. اجرای Backend

برای اجرای Backend:

```powershell
cd F:\project\student-transport
uvicorn app.main:app --reload
```

در صورت اجرای صحیح:

```text
http://127.0.0.1:8000
```

در دسترس است.

Swagger:

```text
http://127.0.0.1:8000/docs
```

است.

---

# 5. Alembic

Alembic برای مدیریت Migrationهای Database استفاده می‌شود.

فایل اصلی:

```text
alembic.ini
```

Migrationها:

```text
alembic/versions/
```

وضعیت شناخته‌شده قبلی:

```text
7f3c2a91d6e4 (head)
```

برای مشاهده وضعیت:

```powershell
alembic current
```

برای مشاهده تاریخچه:

```powershell
alembic history
```

---

# 6. Migrationهای مهم اخیر

Migration مربوط به اطلاعات No-Show:

```text
c1f48139cbb3
```

Migration مربوط به Notification:

```text
4d9a2c8f1b7e
```

Migration مربوط به Boarding Request:

```text
4bc9e57efae5
```

Migration مربوط به تأیید راننده:

```text
3ffe513796d1
```

Migration آخر فیلد زیر را به BoardingRequest اضافه کرد:

```text
requires_driver_approval
```

---

# 7. نکته مهم درباره Alembic

در بررسی‌های قبلی:

```text
alembic check
```

اختلاف‌هایی را نشان داده بود.

این اختلاف‌ها لزوماً مربوط به قابلیت‌های فعلی نبودند.

بنابراین:

> بدون نیاز واقعی، Migration یا Schemaهای unrelated تغییر داده نشوند.

قبل از ساخت Migration جدید ابتدا مشخص شود:

1. مدل واقعاً تغییر کرده است.
2. تغییر موردنیاز پروژه است.
3. تغییر قبلاً در Migration دیگری انجام نشده است.
4. تغییر ناشی از اختلاف محیط یا Database نیست.

---

# 8. Git

Repository:

```text
https://github.com/miyandari/student-transport
```

Branch:

```text
master
```

GitHub در این پروژه برای نگهداری نسخه کنترل‌شده کد استفاده می‌شود.

اما در مقطع فعلی:

> نسخه Local از نسخه موجود در GitHub جلوتر است.

بنابراین نباید فایل‌های قدیمی GitHub بدون بررسی روی Local کپی شوند.

---

# 9. روال Git در پروژه

کاربر تغییرات را در سیستم محلی اعمال می‌کند.

پس از تکمیل یک مرحله:

```powershell
git status
```

بررسی شود.

سپس در صورت تأیید کاربر:

```powershell
git add .
git commit -m "..."
```

و در صورت درخواست صریح کاربر:

```powershell
git push
```

انجام شود.

### قانون مهم

بدون درخواست صریح کاربر:

- Commit انجام نشود.
- Push انجام نشود.
- Branch تغییر نکند.
- History بازنویسی نشود.

---

# 10. Commit فعلی موردنظر

برای تثبیت تغییرات Backend فعلی، Commit پیشنهادی:

```powershell
git add .
git commit -m "Complete backend boarding, notification and trip lifecycle updates"
```

بعد از Commit:

```powershell
git status
git log -1 --oneline
```

بررسی شود.

---

# 11. ساختار همکاری با کاربر

کاربر پروژه را شخصاً در سیستم خود توسعه می‌دهد.

روند همکاری:

```text
بررسی وضعیت
      ↓
انتخاب فایل
      ↓
ارائه تغییر کامل فایل
      ↓
کاربر فایل را جایگزین می‌کند
      ↓
اجرای پروژه / تست
      ↓
گزارش نتیجه
      ↓
فایل بعدی
```

---

# 12. نحوه ارائه کد

کاربر ترجیح می‌دهد کد هر فایل:

**در یک Code Block کامل و یک‌جا** ارائه شود.

بنابراین:

- فایل به چند قطعه تقسیم نشود.
- فقط بخشی از فایل ارائه نشود.
- در صورت تغییر فایل، کل فایل ارائه شود.
- اگر فایل نیاز به تغییر ندارد، دوباره کل فایل ارسال نشود.

---

# 13. میزان توضیحات

کاربر ترجیح می‌دهد هنگام توسعه:

- توضیحات کوتاه باشند.
- مستقیماً وارد کار شویم.
- از توضیحات تکراری خودداری شود.
- مراحل قبلاً انجام‌شده دوباره توضیح داده نشوند.

تمرکز اصلی:

```text
کد → تست → نتیجه → مرحله بعد
```

---

# 14. Local در برابر GitHub

در صورت مشاهده اختلاف بین Local و GitHub:

ابتدا مشخص شود کدام نسخه جدیدتر است.

در وضعیت فعلی:

```text
Local > GitHub
```

بعضی فایل‌های Local هنوز در GitHub نسخه معادل یا نسخه کامل خود را ندارند.

نمونه‌های شناخته‌شده:

```text
app/models/notification.py
app/services/notification_service.py
app/services/student_penalty_service.py
app/services/boarding_request_service.py
app/services/report_service.py
```

همچنین برخی فایل‌های موجود در GitHub نسخه قدیمی‌تری نسبت به Local دارند.

---

# 15. فایل‌های Local-only

در زمان تهیه این مستندات، موارد زیر در Local وجود داشته و در GitHub نسخه مرجع آن‌ها موجود نبوده یا 404 بوده است:

```text
app/models/notification.py
app/services/notification_service.py
app/services/student_penalty_service.py
app/services/boarding_request_service.py
app/services/report_service.py
```

این فهرست ممکن است بعد از Commit و Push تغییر کند.

---

# 16. Backend

Backend مبتنی بر FastAPI است.

اجزای اصلی:

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

اصل معماری:

```text
API
 ↓
Service
 ↓
Model / Database
```

---

# 17. Authentication

احراز هویت با JWT انجام می‌شود.

Roleهای اصلی:

```text
super_admin
university_admin
transport_manager
company_admin
driver
student
```

در Endpointهای حساس:

```text
Authentication
+
Role
+
Scope
```

باید بررسی شوند.

---

# 18. Scope

Scope دسترسی ممکن است شامل:

- University
- Transport Company
- Driver
- Vehicle
- Trip

باشد.

صرف داشتن Role نباید به معنی دسترسی به تمام داده‌ها باشد.

---

# 19. تست Backend

پس از تغییر فایل:

اول Backend اجرا شود:

```powershell
uvicorn app.main:app --reload
```

سپس Swagger بررسی شود:

```text
http://127.0.0.1:8000/docs
```

حداقل باید بررسی شود که:

- Server بالا می‌آید.
- Import Error وجود ندارد.
- Syntax Error وجود ندارد.
- Router جدید بدون خطا Load می‌شود.
- Dependency جدید خطا ایجاد نمی‌کند.

---

# 20. تست سناریویی

بعد از تثبیت Backend باید سناریوهای اصلی تست شوند.

ترتیب پیشنهادی:

```text
Authentication
↓
Student
↓
Service
↓
Trip
↓
Reservation
↓
Boarding
↓
Waitlist
↓
QR
↓
Alighting
↓
No-Show
↓
Notification
↓
Trip Completion
```

---

# 21. تست Reservation

موارد مهم:

- دانشجوی فعال
- دانشجوی غیرفعال
- دانشجوی مسدود
- Reservation تکراری
- جنسیت ناسازگار
- Trip نامعتبر
- لغو Reservation

---

# 22. تست Boarding

موارد مهم:

### صندلی آزاد

باید خودکار تأیید شود.

### صندلی پر و ایستاده آزاد

باید خودکار به حالت ایستاده پذیرفته شود.

### تمام ظرفیت پر

باید Waitlist شود.

### QR

باید نیازمند تأیید راننده باشد.

---

# 23. تست No-Show

در پایان Trip بررسی شود:

```text
Active Reservation
+
No TripPassenger
=
No-Show
```

سپس:

```text
no_show_count += 1
negative_score += 1
```

بررسی شود که:

- بار اول Block نشود.
- بار دوم یک روز Block شود.
- ادامه جدول صحیح باشد.
- جریمه تکراری ثبت نشود.

---

# 24. تست Waitlist

سناریو:

```text
Vehicle Full
↓
Student Request
↓
Waitlist
↓
Passenger Alights
↓
Capacity Available
↓
Promotion
↓
Notification
```

---

# 25. تست QR

سناریو:

```text
Student at Station
↓
Scan QR
↓
Boarding Request
↓
Driver Approves
↓
Boarding Without Reservation
```

بعد از تکمیل Trip:

```text
No-Show نباید ایجاد شود.
```

---

# 26. تست Vehicle Location

بررسی شود:

- Driver مجاز باشد.
- Vehicle صحیح باشد.
- Trip صحیح باشد.
- Assignment صحیح باشد.
- GPS ذخیره شود.
- WebSocket پیام دریافت کند.
- ETA تولید شود.
- Station Event ایجاد شود.
- Notification در صورت نیاز ایجاد شود.

---

# 27. تست Trip Completion

هنگام رسیدن به ایستگاه نهایی:

- Trip باید تکمیل شود.
- No-Show پردازش شود.
- Boarding Requestهای باقی‌مانده مدیریت شوند.
- Notificationهای لازم ارسال شوند.

اگر Endpoint دوباره اجرا شود، عملیات حساس نباید دوباره جریمه ایجاد کند.

---

# 28. خطاهای مهمی که نباید ایجاد شوند

در ادامه توسعه باید از این موارد جلوگیری شود:

- Duplicate Reservation
- Duplicate Boarding
- Duplicate No-Show
- Duplicate Penalty
- دسترسی خارج از Scope
- Boarding بعد از پایان Trip
- Boarding برای دانشجوی مسدود
- Boarding برای جنسیت ناسازگار
- تأیید دستی غیرضروری درخواست عادی
- از بین رفتن Waitlist
- از دست رفتن Assignment جایگزین
- ایجاد Migrationهای غیرضروری

---

# 29. تغییرات Database

قبل از هر تغییر Database:

1. مدل بررسی شود.
2. Migrationهای قبلی بررسی شوند.
3. وضعیت Alembic بررسی شود.
4. تأثیر تغییر روی داده‌های موجود بررسی شود.

از تغییر مستقیم Database تا حد امکان خودداری شود.

اگر تغییر مستقیم برای Recovery ضروری شد، ابتدا باید وضعیت فعلی ثبت شود.

---

# 30. Recovery

در گذشته وضعیت `alembic_version` اصلاح شده بود.

این موضوع نشان می‌دهد که در صورت بروز مشکل Migration:

> ابتدا وضعیت واقعی Database و Alembic بررسی شود و سپس اصلاح انجام شود.

نباید بدون بررسی Migrationها حذف یا دوباره اجرا شوند.

---

# 31. فایل‌های مرجع پروژه

برای ادامه کار، این فایل‌ها در اولویت مطالعه هستند:

```text
docs/project-context/PROJECT_STATUS.md
docs/project-context/NEXT_STEPS.md
docs/project-context/BUSINESS_RULES.md
docs/project-context/ARCHITECTURE.md
docs/project-context/DEVELOPMENT_GUIDE.md
docs/project-context/CHANGELOG.md
```

---

# 32. قانون طلایی ادامه پروژه

در هر چت جدید:

1. وضعیت پروژه خوانده شود.
2. NEXT_STEPS بررسی شود.
3. قوانین BUSINESS_RULES مبنا قرار گیرد.
4. Architecture بررسی شود.
5. Local مبنا قرار گیرد.
6. سپس فقط مرحله بعد انجام شود.

از شروع دوباره مراحل قبلی خودداری شود.

---

# 33. وضعیت فعلی

در زمان ایجاد این فایل:

```text
Backend Core          → عمدتاً تکمیل
Boarding              → تکمیل و در حال تست
Waitlist              → تکمیل و در حال تست
QR                    → تکمیل و در حال تست
No-Show               → تکمیل و در حال تست
Notification          → تکمیل و در حال تست
Trip Lifecycle        → تکمیل و در حال تست
Vehicle Location      → تکمیل و در حال تست
Reports               → پیاده‌سازی شده، نیازمند بازبینی
Backend Tests         → در حال انجام
Frontend               → مرحله بعد
Student App            → مرحله بعد
Driver App             → مرحله بعد
```

---

# 34. دستورالعمل چت جدید

اگر محدودیت چت ایجاد شد، در چت جدید کافی است گفته شود:

```text
پروژه هم‌مسیر را ادامه بده.
مستندات docs/project-context را مبنا قرار بده.
از NEXT_STEPS شروع کن.
```

سپس توسعه باید بدون بازسازی مراحل قبلی ادامه پیدا کند.