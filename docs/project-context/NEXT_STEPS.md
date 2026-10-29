# ادامه پروژه هم‌مسیر

این فایل نقطه شروع ادامه پروژه در چت‌های بعدی است.

## وضعیت فعلی

Backend پروژه بخش عمده قابلیت‌های اصلی را دارد و اکنون در مرحله تثبیت، بازبینی و تست قرار دارد.

نسخه Local از نسخه موجود در GitHub جلوتر است.

بنابراین در ادامه کار:

**نسخه Local مبنا است، نه نسخه قدیمی GitHub.**

---

## اولین اقدام فعلی

قبل از ادامه توسعه، تغییرات فعلی Local باید Commit شوند.

در PowerShell:

```powershell
cd F:\project\student-transport
git status
git add .
git commit -m "Complete backend boarding, notification and trip lifecycle updates"
git status
git log -1 --oneline
```

فعلاً Push انجام نشود، مگر اینکه کاربر صراحتاً درخواست کند.

---

# مرحله بعد از Commit

پس از Commit، بازبینی Backend از همان نقطه ادامه پیدا کند.

ترتیب پیشنهادی:

1. بررسی وضعیت Git
2. بررسی فایل‌های Backend باقی‌مانده
3. بررسی APIها و Schemaهای باقی‌مانده
4. تست Reservation
5. تست Boarding Request
6. تست ظرفیت صندلی و ایستاده
7. تست Waitlist
8. تست QR
9. تست No-Show
10. تست مسدودی دانشجو
11. تست Trip Lifecycle
12. تست Vehicle Location و WebSocket
13. تست ETA
14. تست Incident و جایگزینی خودرو/راننده
15. تست Notification
16. بررسی Reports
17. تکمیل Backend
18. سپس شروع Frontend / اپ دانشجو / اپ راننده

---

# سناریوهای حیاتی برای تست

## 1. صندلی خالی

```text
Student
   ↓
درخواست عادی
   ↓
تأیید خودکار
   ↓
Boarding
```

راننده نباید نیاز به تأیید دستی داشته باشد.

---

## 2. صندلی پر ولی ظرفیت ایستاده موجود

```text
Student
   ↓
درخواست عادی
   ↓
تأیید خودکار
   ↓
Boarding به‌صورت ایستاده
```

در این حالت نیز راننده نباید نیاز به تأیید داشته باشد.

---

## 3. تمام ظرفیت پر

```text
Student
   ↓
درخواست عادی
   ↓
Waitlist
```

درخواست عادی نباید برای تأیید راننده ارسال شود.

---

## 4. آزادشدن ظرفیت

وقتی مسافر پیاده شد:

```text
Alight
   ↓
بررسی Waitlist
   ↓
Promotion
   ↓
Boarding
   ↓
Notification
```

---

## 5. QR بدون رزرو

```text
Student
   ↓
Scan QR
   ↓
Boarding Request
   ↓
Driver Approval
   ↓
Approve / Reject
```

در صورت تأیید:

```text
boarding_without_reservation
```

ثبت شود.

این حالت نباید باعث No-Show شود.

---

## 6. No-Show

هنگام تکمیل Trip:

```text
Trip Complete
   ↓
Reservation فعال؟
   ↓
Boarding ثبت نشده؟
   ↓
No-Show
```

سپس:

```text
no_show_count += 1
negative_score += 1
```

مسدودی طبق جدول زیر:

| No-Show | مسدودی |
|---|---:|
| اول | ۰ روز |
| دوم | ۱ روز |
| سوم | ۳ روز |
| چهارم | ۵ روز |
| پنجم | ۷ روز |
| ششم و بیشتر | ۱۴ روز |

---

## 7. جلوگیری از جریمه تکراری

اگر Endpoint تکمیل Trip دوبار اجرا شود:

```text
No-Show نباید دوباره ثبت شود.
```

AuditLog باید برای جلوگیری از Duplicate Penalty بررسی شود.

---

## 8. دانشجوی مسدود

دانشجوی مسدود نباید بتواند درخواست جدید سرویس ثبت کند.

انتظار:

```text
HTTP 403
```

---

## 9. لغو Reservation

لغو Reservation:

```text
No-Show نیست
```

نباید امتیاز منفی ایجاد کند.

---

## 10. Waitlist

Waitlist:

```text
No-Show نیست
```

---

## 11. جنسیت

دانشجو نباید بتواند برای سرویس ناسازگار با جنسیت خود درخواست ثبت کند.

---

## 12. Isolation

باید بررسی شود که:

- University Admin فقط اطلاعات دانشگاه خودش را ببیند.
- Company Admin فقط اطلاعات شرکت خودش را ببیند.
- Driver فقط اطلاعات سفر/خودروی مجاز خودش را ببیند.
- Student فقط اطلاعات خودش و سرویس‌های مجاز را ببیند.

---

# قابلیت‌هایی که نباید دوباره طراحی شوند

قابلیت‌های زیر قبلاً طراحی و پیاده‌سازی شده‌اند و در ادامه نباید بدون دلیل دوباره از صفر طراحی شوند:

- Reservation
- Boarding Request
- Waitlist
- QR Boarding
- Trip Passenger
- No-Show
- Student Penalty
- Notification
- Vehicle Location
- ETA
- Trip Lifecycle
- Trip Assignment
- Trip Incident
- Reports

در صورت مشاهده مشکل، ابتدا همان پیاده‌سازی موجود اصلاح شود.

---

# فایل‌های مهم Local

فایل‌های مهمی که نسخه Local آن‌ها نسبت به GitHub جلوتر است یا Local-only هستند:

```text
app/models/notification.py
app/services/notification_service.py
app/services/student_penalty_service.py
app/services/boarding_request_service.py
app/services/report_service.py
```

همچنین برخی فایل‌های API و Service نسخه Local کامل‌تری نسبت به GitHub دارند.

---

# نکات مهم هنگام ادامه توسعه

## Local اولویت دارد

اگر بین GitHub و Local اختلاف وجود داشت:

```text
Local > GitHub
```

تا زمانی که Commit جدید تثبیت شود.

## تغییر فایل

هر بار فقط فایل موردنیاز تغییر کند.

اگر فایل نیاز به تغییر داشت:

**کل فایل در یک Code Block ارائه شود.**

کد یک فایل به چند قسمت تقسیم نشود.

## فایل بدون تغییر

اگر فایل نیاز به تغییر ندارد، دوباره کل آن برای کاربر ارسال نشود.

## Migration

Migration جدید فقط زمانی ایجاد شود که واقعاً لازم باشد.

اختلاف‌های unrelated مربوط به Alembic نباید وارد کار جاری شوند.

## Git

Commit و Push توسط کاربر انجام می‌شود، مگر اینکه کاربر صراحتاً درخواست دیگری بدهد.

---

# ادامه در چت جدید

اگر محدودیت چت فعلی تمام شد، در چت جدید ابتدا این فایل‌ها بررسی شوند:

```text
docs/project-context/PROJECT_STATUS.md
docs/project-context/NEXT_STEPS.md
docs/project-context/BUSINESS_RULES.md
docs/project-context/ARCHITECTURE.md
docs/project-context/DEVELOPMENT_GUIDE.md
docs/project-context/CHANGELOG.md
```

بعد کار دقیقاً از آخرین وضعیت همین فایل‌ها ادامه پیدا کند.

---

# جمله پیشنهادی برای شروع چت جدید

```text
پروژه «هم‌مسیر» را ادامه بده.
فایل‌های docs/project-context را مبنا قرار بده.
ابتدا PROJECT_STATUS و NEXT_STEPS را بررسی کن و از آخرین مرحله ادامه بده.
