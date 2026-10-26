from app.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
from app.core.roles import Roles


USERNAME = "admin"
INITIAL_PASSWORD = "Admin@123456"


db = SessionLocal()

try:
    existing_admin = (
        db.query(User)
        .filter(
            User.username == USERNAME
        )
        .first()
    )

    if existing_admin:
        print(
            f"کاربر '{USERNAME}' قبلاً وجود دارد و کاربر جدیدی ایجاد نشد."
        )
    else:
        admin = User(
            username=USERNAME,
            password_hash=hash_password(
                INITIAL_PASSWORD
            ),
            first_name="مدیر",
            last_name="سامانه",
            phone=None,
            role=Roles.SUPER_ADMIN,
            university_id=None,
            student_id=None,
            driver_id=None,
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(
            f"کاربر مدیر '{USERNAME}' با موفقیت ایجاد شد."
        )

finally:
    db.close()