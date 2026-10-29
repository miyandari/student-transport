# تاریخچه تغییرات پروژه هم‌مسیر

این فایل خلاصه‌ای از مراحل مهم توسعه پروژه را نگهداری می‌کند تا در ادامه پروژه مشخص باشد چه قابلیت‌هایی ایجاد یا اصلاح شده‌اند.

---

# 2026-10-29

## وضعیت Backend

Backend وارد مرحله تثبیت و بازبینی شد.

قابلیت‌های اصلی پیاده‌سازی‌شده:

- Authentication و مدیریت Role
- مدیریت دانشگاه
- مدیریت دانشجو
- مدیریت شرکت حمل‌ونقل
- مدیریت قرارداد
- مدیریت راننده
- مدیریت خودرو
- مدیریت ایستگاه
- مدیریت مسیر
- مدیریت سرویس
- Schedule
- Trip
- Trip Assignment
- Reservation
- Trip Passenger
- Vehicle Location
- ETA
- Station Event
- Trip Incident
- Feedback
- AuditLog
- Notification
- Boarding Request
- Student Penalty
- Reports

---

# 2026-10-29 — Boarding Request

منطق Boarding Request تکمیل شد.

## درخواست عادی

درخواست عادی دانشجو:

- نیاز به تأیید راننده ندارد.
- در صورت وجود ظرفیت صندلی، خودکار پذیرفته می‌شود.
- در صورت پر بودن صندلی و وجود ظرفیت ایستاده، می‌تواند به‌صورت ایستاده پذیرفته شود.
- در صورت تکمیل کامل ظرفیت، وارد Waitlist می‌شود.

---

# 2026-10-29 — QR Boarding

مسیر QR از درخواست عادی جدا شد.

در QR بدون Reservation:

```text
Student
↓
Scan QR
↓
Boarding Request
↓
Driver Approval
↓
Boarding
```

فیلد زیر به BoardingRequest اضافه شد:

```text
requires_driver_approval
```

برای درخواست‌های QR مقدار آن:

```text
true
```

و برای درخواست‌های عادی:

```text
false
```

است.

---

# 2026-10-29 — Migration مربوط به Boarding Approval

Migration:

```text
3ffe513796d1
```

از Migration:

```text
4bc9e57efae5
```

ایجاد شد.

تغییر اصلی:

```text
boarding_requests.requires_driver_approval
```

به همراه Index مربوطه.

---

# 2026-10-29 — Waitlist

منطق Waitlist تکمیل شد.

در صورت آزادشدن ظرفیت:

- درخواست‌های عادی pending بررسی می‌شوند.
- ظرفیت مجدداً بررسی می‌شود.
- دانشجو در صورت امکان خودکار ارتقا پیدا می‌کند.
- TripPassenger ایجاد می‌شود.
- BoardingRequest تأیید می‌شود.
- Notification برای دانشجو ایجاد می‌شود.

Waitlist No-Show محسوب نمی‌شود.

---

# 2026-10-29 — Student Penalty

Service مربوط به جریمه دانشجو ایجاد/تکمیل شد:

```text
app/services/student_penalty_service.py
```

وظایف:

- ثبت No-Show
- افزایش `no_show_count`
- افزایش `negative_score`
- محاسبه مدت مسدودی
- بررسی مسدودی فعال

---

# 2026-10-29 — No-Show

منطق No-Show در Trip Lifecycle تکمیل شد.

No-Show زمانی ثبت می‌شود که:

- Reservation فعال باشد.
- Trip به پایان برسد.
- دانشجو Boarding نشده باشد.

برای جلوگیری از جریمه دوباره، AuditLog بررسی می‌شود.

Action مورد استفاده برای تشخیص جریمه:

```text
no_show_penalty
```

---

# 2026-10-29 — جدول مسدودی

قوانین مسدودی:

| No-Show | مدت مسدودی |
|---|---:|
| اول | ۰ روز |
| دوم | ۱ روز |
| سوم | ۳ روز |
| چهارم | ۵ روز |
| پنجم | ۷ روز |
| ششم و بیشتر | ۱۴ روز |

هر No-Show:

```text
no_show_count += 1
negative_score += 1
```

---

# 2026-10-29 — Student Model

فیلدهای زیر به Student اضافه شدند:

```text
no_show_count
negative_score
blocked_until
```

همچنین Constraintهای مربوط به غیرمنفی بودن مقادیر اضافه شدند.

---

# 2026-10-29 — Migration مربوط به Student Penalty

Migration:

```text
c1f48139cbb3
```

برای افزودن فیلدهای مربوط به No-Show و مسدودی ایجاد شد.

---

# 2026-10-29 — Notification

Notification به پروژه اضافه شد.

مدل:

```text
app/models/notification.py
```

Schema:

```text
app/schemas/notification.py
```

Service:

```text
app/services/notification_service.py
```

API:

```text
app/api/notifications.py
```

قابلیت‌های اصلی:

- دریافت Notificationها
- دریافت تعداد Notificationهای خوانده‌نشده
- علامت‌گذاری یک Notification به‌عنوان خوانده‌شده
- علامت‌گذاری همه Notificationها
- Notification برای دانشجو
- Notification نزدیک ایستگاه
- Notification تقاضای زیاد
- Notification استفاده کم از مسیر

---

# 2026-10-29 — Notification Migration

Migration:

```text
4d9a2c8f1b7e
```

برای ایجاد جدول Notification اجرا شد.

---

# 2026-10-29 — Vehicle Location

Vehicle Location Service توسعه یافت تا علاوه بر ثبت GPS:

- Assignment فعال را بررسی کند.
- موقعیت را از طریق WebSocket منتشر کند.
- ETA را محاسبه کند.
- نزدیک‌شدن به ایستگاه را تشخیص دهد.
- Notification ایجاد کند.
- رسیدن به ایستگاه را پردازش کند.
- در صورت رسیدن به ایستگاه نهایی، Trip را تکمیل کند.

---

# 2026-10-29 — Trip Lifecycle

Trip Lifecycle توسعه یافت.

قابلیت‌های اضافه‌شده:

- تکمیل Trip
- پردازش No-Show
- جلوگیری از No-Show تکراری
- لغو Boarding Requestهای pending هنگام پایان Trip
- Notification مرتبط
- بررسی استفاده کم از مسیر

---

# 2026-10-29 — Trip Incident

Trip Incident توسعه یافت.

قابلیت‌ها:

- ایجاد Incident
- دریافت Incident
- Resolve کردن Incident
- تعیین راننده جایگزین
- تعیین خودرو جایگزین
- جایگزینی هر دو
- حفظ Resource فعلی در صورت جایگزینی فقط یکی از آن‌ها

---

# 2026-10-29 — Reports

Service گزارش‌ها ایجاد شد:

```text
app/services/report_service.py
```

گزارش‌های موجود:

- Transport Summary
- Financial Report
- Route Usage
- Driver Performance
- Vehicle Usage

API گزارش‌ها:

```text
app/api/reports.py
```

این بخش هنوز نیاز به بازبینی و تست دقیق‌تر دارد.

---

# 2026-10-29 — Reservation

کنترل مسدودی دانشجو به Reservation اضافه شد.

در زمان ایجاد Reservation:

```text
validate_student_not_blocked()
```

بررسی می‌شود.

دانشجوی مسدود نمی‌تواند Reservation جدید ثبت کند.

---

# 2026-10-29 — WebSocket

WebSocket موقعیت خودرو تثبیت شد.

Endpoint:

```text
/ws/trips/{trip_id}/location
```

موارد کنترل:

- JWT
- User
- Role
- University
- Company
- Trip
- Driver
- Vehicle

---

# 2026-10-29 — ETA

ETA Service بررسی و تثبیت شد.

ویژگی‌ها:

- آخرین GPS
- سرعت معتبر
- جهت حرکت
- فاصله تا ایستگاه
- Route Progress
- Next Station
- GPS freshness
- وضعیت offline/stale

---

# 2026-10-29 — Database

PostgreSQL:

```text
17.11
```

به‌عنوان Database اصلی پروژه استفاده می‌شود.

---

# 2026-10-29 — Development Environment

محیط توسعه فعلی:

```text
Python 3.13.9
.venv313
PostgreSQL 17.11
```

مسیر:

```text
F:\project\student-transport
```

---

# 2026-10-29 — Git وضعیت پروژه

نسخه GitHub در مرحله قبلی:

```text
baaff7f
```

بود.

اما Local در ادامه توسعه تغییرات بیشتری دریافت کرد.

در نتیجه:

```text
Local > GitHub
```

و قبل از ادامه توسعه باید تغییرات Local در Commit تثبیت شوند.

Commit پیشنهادی:

```text
Complete backend boarding, notification and trip lifecycle updates
```

---

# Migration History

## c1f48139cbb3

افزودن اطلاعات No-Show و مسدودی به Student.

## 4d9a2c8f1b7e

افزودن Notification.

## 4bc9e57efae5

افزودن Boarding Request.

## 3ffe513796d1

افزودن `requires_driver_approval`.

---

# وضعیت فعلی قابلیت‌ها

| قابلیت | وضعیت |
|---|---|
| Authentication | پیاده‌سازی شده |
| Role Management | پیاده‌سازی شده |
| University | پیاده‌سازی شده |
| Student | پیاده‌سازی شده |
| Driver | پیاده‌سازی شده |
| Company | پیاده‌سازی شده |
| Vehicle | پیاده‌سازی شده |
| Route | پیاده‌سازی شده |
| Station | پیاده‌سازی شده |
| Service | پیاده‌سازی شده |
| Schedule | پیاده‌سازی شده |
| Trip | پیاده‌سازی شده |
| Trip Assignment | پیاده‌سازی شده |
| Reservation | پیاده‌سازی شده |
| Boarding Request | پیاده‌سازی شده |
| Waitlist | پیاده‌سازی شده |
| QR Boarding | پیاده‌سازی شده |
| Trip Passenger | پیاده‌سازی شده |
| No-Show | پیاده‌سازی شده |
| Student Penalty | پیاده‌سازی شده |
| Notification | پیاده‌سازی شده |
| Vehicle Location | پیاده‌سازی شده |
| WebSocket | پیاده‌سازی شده |
| ETA | پیاده‌سازی شده |
| Station Event | پیاده‌سازی شده |
| Trip Incident | پیاده‌سازی شده |
| Reports | پیاده‌سازی شده، نیازمند بازبینی |
| Frontend | مرحله بعد |
| Student App | مرحله بعد |
| Driver App | مرحله بعد |

---

# مرحله بعد

بعد از تثبیت Commit فعلی:

1. تکمیل بازبینی Backend
2. تست سناریوهای اصلی
3. اصلاح خطاهای احتمالی
4. تست APIها
5. تست Trip Lifecycle
6. تست Reservation / Boarding / QR / Waitlist
7. تست No-Show
8. تست Notification
9. تست Reports
10. آماده‌سازی Frontend و اپ‌های دانشجو و راننده

---

# نکته پایانی

این فایل تاریخچه خلاصه پروژه است.

جزئیات قوانین کسب‌وکار در:

```text
docs/project-context/BUSINESS_RULES.md
```

معماری در:

```text
docs/project-context/ARCHITECTURE.md
```

و وضعیت فعلی و مرحله بعد در:

```text
docs/project-context/PROJECT_STATUS.md
docs/project-context/NEXT_STEPS.md
```

نگهداری می‌شود.