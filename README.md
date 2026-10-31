# هم‌مسیر — Backend

سامانه مدیریت سرویس ایاب‌وذهاب دانشجویی. ساخته‌شده با FastAPI، SQLAlchemy و PostgreSQL.

اپ موبایل (Flutter): [student-transport-mobile](https://github.com/miyandari/student-transport-mobile)

## راه‌اندازی

1. ساخت محیط مجازی و نصب وابستگی‌ها:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # ویندوز
   pip install -r requirements.txt
   ```

2. ساخت دیتابیس PostgreSQL با نام `student_transport`.

3. ساخت فایل `.env` از روی نمونه و پر کردن مقادیر:

   ```bash
   copy .env.example .env        # ویندوز
   ```

   - `DATABASE_URL`: آدرس اتصال به دیتابیس
   - `SECRET_KEY`: کلید JWT (با `python -c "import secrets; print(secrets.token_urlsafe(48))"` بسازید)

4. اجرای مایگریشن‌ها:

   ```bash
   alembic upgrade head
   ```

5. ساخت ادمین اولیه (رمز را بعد از اولین ورود حتماً عوض کنید) و داده‌ی آزمایشی:

   ```bash
   python create_admin.py
   python create_test_data.py   # فقط برای توسعه
   ```

6. اجرای سرور:

   ```bash
   uvicorn app.main:app --reload
   ```

   مستندات Swagger: http://127.0.0.1:8000/docs

## ساختار

```text
app/api/        endpointها (FastAPI routers)
app/services/   منطق کسب‌وکار (رزرو، Boarding، No-Show، ETA، ...)
app/models/     مدل‌های SQLAlchemy
app/schemas/    مدل‌های Pydantic
app/core/       امنیت، نقش‌ها و dependencyهای دسترسی
app/realtime/   مدیریت اتصال WebSocket
alembic/        مایگریشن‌ها
docs/           مستندات پروژه (معماری، قوانین کسب‌وکار، وضعیت و گام‌های بعدی)
```

برای جزئیات کامل به پوشه‌ی `docs/project-context` مراجعه کنید.

## نکات امنیتی

- فایل `.env` را هرگز commit نکنید.
- رمزهای پیش‌فرض `create_admin.py` و `create_test_data.py` فقط برای توسعه‌اند.
