import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from jose import jwt


load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY or not SECRET_KEY.strip():
    raise RuntimeError(
        "SECRET_KEY در فایل .env تنظیم نشده است"
    )

SECRET_KEY = SECRET_KEY.strip()

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str) -> str:
    """
    تبدیل رمز عبور خام به hash امن با bcrypt.
    """

    if not password:
        raise ValueError(
            "رمز عبور نمی‌تواند خالی باشد"
        )

    password_bytes = password.encode("utf-8")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    بررسی رمز عبور خام در برابر hash ذخیره‌شده.
    """

    if not plain_password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    ایجاد JWT Access Token با زمان انقضای مشخص.
    """

    if not isinstance(data, dict):
        raise TypeError(
            "اطلاعات توکن باید از نوع dict باشد"
        )

    if "sub" not in data:
        raise ValueError(
            "توکن باید دارای شناسه کاربر (sub) باشد"
        )

    if data["sub"] is None:
        raise ValueError(
            "شناسه کاربر (sub) نمی‌تواند خالی باشد"
        )

    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode["exp"] = expire

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )