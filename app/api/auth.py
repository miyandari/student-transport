from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.core.security import verify_password, create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
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
            User.username == form_data.username
        )
        .first()
    )

    # --------------------------------
    # بررسی کاربر و رمز عبور
    # --------------------------------

    # پیام خطا در حالت کاربر ناموجود،
    # حساب غیرفعال و رمز عبور اشتباه یکسان است
    # تا وجود یا وضعیت حساب افشا نشود.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # ابتدا رمز عبور بررسی می‌شود.
    # حتی برای حساب غیرفعال نیز رمز اشتباه نباید
    # باعث افشای وضعیت حساب شود.
    password_is_valid = verify_password(
        form_data.password,
        user.password_hash,
    )

    if not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # --------------------------------
    # بررسی فعال بودن حساب
    # --------------------------------

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

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
