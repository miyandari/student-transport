## وصله‌ی ۱ — بارگذاری گروهی دانشجو
app/api/student_import.py

## وصله‌ی ۲ — نرخ سفر به‌ازای نوع خودرو + گزارش هزینه
فایل‌های جدید: app/models/contract_rate.py ، app/api/contract_rates.py ، alembic/versions/c7a1e4d2b903_create_contract_rates.py
تغییر در app/models/__init__.py (یک خط import در انتها) و app/main.py:
   from app.api.student_import import router as student_import_router
   from app.api.contract_rates import router as contract_rates_router
   app.include_router(student_import_router)
   app.include_router(contract_rates_router)
اجرا:  alembic upgrade head      (down_revision = b51825dfc407؛ اگر head شما فرق دارد، همین مقدار را اصلاح کنید)
create_demo_data.py: دو نرخ نمونه (bus و minibus) اضافه شده.

تست‌شده روی SQLite: ثبت/ویرایش نرخ، محاسبه‌ی هزینه، سفر بدون نرخ، 403 برای راننده، فقط‌خواندن برای کاربر شرکت، 422 برای نرخ منفی.
تست نشده: migration روی PostgreSQL (روی SQLite با create_all تست شد).

git:
git add app/api/student_import.py app/api/contract_rates.py app/models/contract_rate.py app/models/__init__.py app/main.py alembic/versions/c7a1e4d2b903_create_contract_rates.py create_demo_data.py
git commit -m "Add student import and contract rates"
git push
(فایل .env را هرگز اضافه نکنید)
