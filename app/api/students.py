from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student import Student
from app.models.user import User
from app.models.university import University
from app.schemas.student import StudentCreate, StudentResponse
from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.services.student_qr_service import (
    ensure_student_qr_token,
    regenerate_student_qr_token,
)


router = APIRouter(
    prefix="/students",
    tags=["Students"]
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}


def check_university_access(
    current_user: User,
    university_id: int,
):
    if current_user.role == Roles.SUPER_ADMIN:
        return

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست"
        )

    if current_user.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به اطلاعات این دانشگاه دسترسی ندارید"
        )


def normalize_text(value: str | None):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def get_active_university(
    db: Session,
    university_id: int,
):
    university = (
        db.query(University)
        .filter(
            University.id == university_id
        )
        .first()
    )

    if university is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشگاه پیدا نشد"
        )

    if not university.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه انتخاب‌شده فعال نیست"
        )

    return university


def get_student_or_404(
    db: Session,
    student_id: int,
) -> Student:
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو پیدا نشد"
        )

    return student


@router.post(
    "/",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED
)
def create_student(
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد دانشجو را ندارید"
        )

    check_university_access(
        current_user,
        student_data.university_id
    )

    get_active_university(
        db,
        student_data.university_id
    )

    student_number = normalize_text(
        student_data.student_number
    )

    first_name = normalize_text(
        student_data.first_name
    )

    last_name = normalize_text(
        student_data.last_name
    )

    gender = normalize_text(
        student_data.gender
    )

    national_id = normalize_text(
        student_data.national_id
    )

    phone = normalize_text(
        student_data.phone
    )

    if not student_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره دانشجویی نمی‌تواند خالی باشد"
        )

    if not first_name or not last_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام و نام خانوادگی نمی‌توانند خالی باشند"
        )

    if gender not in {"male", "female"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="جنسیت دانشجو نامعتبر است"
        )

    existing_student = (
        db.query(Student)
        .filter(
            Student.university_id == student_data.university_id,
            Student.student_number == student_number
        )
        .first()
    )

    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این شماره دانشجویی قبلاً در این دانشگاه ثبت شده است"
        )

    if national_id:
        existing_national_id = (
            db.query(Student)
            .filter(
                Student.national_id == national_id
            )
            .first()
        )

        if existing_national_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این کد ملی قبلاً ثبت شده است"
            )

    student = Student(
        university_id=student_data.university_id,
        student_number=student_number,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        national_id=national_id,
        phone=phone,
        is_active=student_data.is_active,
    )

    try:
        db.add(student)
        db.flush()

        ensure_student_qr_token(
            db,
            student,
        )

        db.commit()
        db.refresh(student)

    except Exception:
        db.rollback()
        raise

    return student


@router.get(
    "/",
    response_model=list[StudentResponse]
)
def get_students(
    university_id: int | None = None,
    student_number: str | None = None,
    is_active: bool | None = None,
    gender: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده دانشجویان را ندارید"
        )

    query = db.query(Student)

    if current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست"
            )

        query = query.filter(
            Student.university_id == current_user.university_id
        )

    elif university_id is not None:
        query = query.filter(
            Student.university_id == university_id
        )

    if student_number is not None:
        normalized_student_number = normalize_text(
            student_number
        )

        if normalized_student_number:
            query = query.filter(
                Student.student_number
                == normalized_student_number
            )

    if gender is not None:
        normalized_gender = normalize_text(gender)

        if normalized_gender not in {"male", "female"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="جنسیت نامعتبر است"
            )

        query = query.filter(
            Student.gender == normalized_gender
        )

    if is_active is not None:
        query = query.filter(
            Student.is_active == is_active
        )

    return (
        query
        .order_by(Student.id.desc())
        .all()
    )


@router.get(
    "/{student_id}",
    response_model=StudentResponse
)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این دانشجو را ندارید"
        )

    student = get_student_or_404(
        db,
        student_id,
    )

    check_university_access(
        current_user,
        student.university_id
    )

    return student


@router.get(
    "/{student_id}/qr"
)
def get_student_qr(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = get_student_or_404(
        db,
        student_id,
    )

    if current_user.role in MANAGEMENT_ROLES:
        check_university_access(
            current_user,
            student.university_id
        )

    elif current_user.role == Roles.STUDENT:

        if current_user.student_id != student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط به QR خودتان دسترسی دارید"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده QR دانشجو را ندارید"
        )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی غیرفعال نمی‌تواند QR فعال داشته باشد"
        )

    student = ensure_student_qr_token(
        db,
        student,
    )

    return {
        "student_id": student.id,
        "qr_token": student.qr_token,
    }


@router.get(
    "/me/qr"
)
def get_my_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != Roles.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این بخش فقط برای دانشجویان است"
        )

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حساب کاربری به دانشجو متصل نیست"
        )

    student = get_student_or_404(
        db,
        current_user.student_id,
    )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی غیرفعال نمی‌تواند QR فعال داشته باشد"
        )

    student = ensure_student_qr_token(
        db,
        student,
    )

    return {
        "student_id": student.id,
        "qr_token": student.qr_token,
    }


@router.post(
    "/{student_id}/qr/regenerate"
)
def regenerate_student_qr(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر QR دانشجو را ندارید"
        )

    student = get_student_or_404(
        db,
        student_id,
    )

    check_university_access(
        current_user,
        student.university_id
    )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی غیرفعال نمی‌تواند QR فعال داشته باشد"
        )

    student = regenerate_student_qr_token(
        db,
        student,
    )

    return {
        "student_id": student.id,
        "qr_token": student.qr_token,
    }


@router.patch(
    "/{student_id}/status",
    response_model=StudentResponse
)
def update_student_status(
    student_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت دانشجو را ندارید"
        )

    student = get_student_or_404(
        db,
        student_id,
    )

    check_university_access(
        current_user,
        student.university_id
    )

    student.is_active = is_active

    try:
        db.commit()
        db.refresh(student)
    except Exception:
        db.rollback()
        raise

    return student


@router.patch(
    "/{student_id}",
    response_model=StudentResponse
)
def update_student(
    student_id: int,
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش دانشجو را ندارید"
        )

    student = get_student_or_404(
        db,
        student_id,
    )

    check_university_access(
        current_user,
        student.university_id
    )

    if student_data.university_id != student.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه دانشجو از این بخش وجود ندارد"
        )

    get_active_university(
        db,
        student.university_id
    )

    student_number = normalize_text(
        student_data.student_number
    )

    first_name = normalize_text(
        student_data.first_name
    )

    last_name = normalize_text(
        student_data.last_name
    )

    gender = normalize_text(
        student_data.gender
    )

    national_id = normalize_text(
        student_data.national_id
    )

    phone = normalize_text(
        student_data.phone
    )

    if not student_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره دانشجویی نمی‌تواند خالی باشد"
        )

    if not first_name or not last_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام و نام خانوادگی نمی‌توانند خالی باشند"
        )

    if gender not in {"male", "female"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="جنسیت دانشجو نامعتبر است"
        )

    existing_student = (
        db.query(Student)
        .filter(
            Student.university_id == student.university_id,
            Student.student_number == student_number,
            Student.id != student.id
        )
        .first()
    )

    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این شماره دانشجویی قبلاً در این دانشگاه ثبت شده است"
        )

    if national_id:
        existing_national_id = (
            db.query(Student)
            .filter(
                Student.national_id == national_id,
                Student.id != student.id
            )
            .first()
        )

        if existing_national_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این کد ملی قبلاً ثبت شده است"
            )

    student.student_number = student_number
    student.first_name = first_name
    student.last_name = last_name
    student.gender = gender
    student.national_id = national_id
    student.phone = phone
    student.is_active = student_data.is_active

    try:
        db.commit()
        db.refresh(student)
    except Exception:
        db.rollback()
        raise

    return student