# پچ بک‌اند برای اپ راننده

## فایل‌ها
1. `app/api/driver_self.py` (جدید) ← کپی در `app/api/`
2. `app/main.py` — دو خط:
   ```python
   from app.api.driver_self import router as driver_self_router
   ...
   app.include_router(driver_self_router)   # بعد از student_self_router و قبل از students_router
   ```
3. `app/services/trip_service.py` در `apply_status_transition`، شاخه‌ی `in_progress`:
   ```python
   planned = trip.planned_departure_time
   if planned.tzinfo is None:
       planned = planned.replace(tzinfo=timezone.utc)
   trip.actual_departure_time = max(now, planned)
   ```
   (بدون آن، حرکت زودتر از ساعت برنامه‌ای خطای ۴۰۰ «ناسازگاری اطلاعات» می‌دهد.)
4. `create_demo_data.py` (به‌روز) — راننده‌ها `driver1..driver8` با رمز `Driver@123`.

نمونه‌ی diff در `driver_patch.diff` (شامل `student_self` اگر قبلاً اعمال نکرده‌اید).

## اندپوینت‌ها (`/driver`)
`GET /me` · `GET /trips?days=` · `GET /trips/{id}` · `POST /trips/{id}/status` · `GET /trips/{id}/manifest` ·
`POST /trips/{id}/locations` (دسته‌ای تا ۱۰۰ نقطه) · `POST /trips/{id}/breakdown`

خرابی: `TripIncident(incident_type="vehicle_breakdown:<kind>")` + اعلان `trip_breakdown_manager` برای مدیران و
`trip_breakdown` برای دانشجویان رزروکرده.

## تست
تست یکپارچه روی SQLite انجام شده (me، trips، locations، manifest، breakdown، چرخه‌ی وضعیت، ۴۰۳ برای سفر دیگران/دانشجو).
روی PostgreSQL هنوز تست نشده.
