from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.core.security import verify_password, create_access_token, bcrypt


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# برای جلوگیری از تفاوت محسوس زمان پاسخ بین
# «کاربر موجود» و «کاربر ناموجود».
#
# این hash فقط برای بررسی dummy استفاده می‌شود
# و هرگز نباید به‌عنوان رمز عبور واقعی استفاده شود.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"invalid-login-dummy-password",
    bcrypt.gensalt(),
).decode("utf-8")


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="نام کاربری یا رمز عبور اشتباه است",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # --------------------------------
    # پیدا کردن کاربر
    # --------------------------------

    user = (
        db.query(User)
        .filter(
            User.username == form_data.username,
        )
        .first()
    )

    # --------------------------------
    # بررسی رمز عبور
    # --------------------------------

    if user is None:

        # حتی در صورت نبودن کاربر، bcrypt اجرا می‌شود
        # تا زمان پاسخ قابل مقایسه با حساب واقعی باشد.
        verify_password(
            form_data.password,
            DUMMY_PASSWORD_HASH,
        )

        raise invalid_credentials()

    password_is_valid = verify_password(
        form_data.password,
        user.password_hash,
    )

    if not password_is_valid:
        raise invalid_credentials()

    # --------------------------------
    # بررسی فعال بودن حساب
    # --------------------------------

    if not user.is_active:
        raise invalid_credentials()

    # --------------------------------
    # ایجاد Access Token
    # --------------------------------

    access_token = create_access_token(
        data={
            "sub": str(user.id),
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
