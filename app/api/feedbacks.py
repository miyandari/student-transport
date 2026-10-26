from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_trip_company_access,
)

from app.core.roles import Roles

from app.services.feedback_service import (
    get_trip,
    get_student,
    get_feedback,
    create_feedback,
    get_feedbacks,
    resolve_feedback,
)


router = APIRouter(
    prefix="/feedbacks",
    tags=["Feedbacks"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}

CREATE_ROLES = MANAGEMENT_ROLES | {
    Roles.STUDENT,
}

VIEW_ROLES = CREATE_ROLES | {
    Roles.COMPANY_ADMIN,
}

RESOLVE_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


def check_trip_access(
    db: Session,
    current_user: User,
    trip,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db,
            current_user,
            trip,
        )

    else:

        check_university_access(
            current_user=current_user,
            university_id=trip.university_id,
        )


@router.post(
    "/",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback_endpoint(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in CREATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ثبت بازخورد ندارید",
        )

    trip = get_trip(
        db,
        feedback_data.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    # -------------------------------------------------
    # دانشجو فقط برای خودش می‌تواند بازخورد ثبت کند.
    # -------------------------------------------------

    if current_user.role == Roles.STUDENT:

        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به یک دانشجو متصل نیست",
            )

        if feedback_data.student_id != current_user.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید برای حساب خودتان بازخورد ثبت کنید",
            )

    # -------------------------------------------------
    # بررسی دانشجو
    # -------------------------------------------------

    student = get_student(
        db,
        feedback_data.student_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=student.university_id,
    )

    # اطمینان از اینکه دانشجو و سفر متعلق به
    # یک دانشگاه هستند.
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو و سفر متعلق به یک دانشگاه نیستند",
        )

    feedback = create_feedback(
        db,
        trip_id=feedback_data.trip_id,
        student_id=feedback_data.student_id,
        rating=feedback_data.rating,
        feedback_type=feedback_data.feedback_type,
        title=feedback_data.title,
        message=feedback_data.message,
    )

    return feedback


@router.get(
    "/",
    response_model=list[FeedbackResponse],
)
def get_feedbacks_endpoint(
    trip_id: int | None = None,
    student_id: int | None = None,
    feedback_type: str | None = None,
    is_resolved: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده بازخوردها را ندارید",
        )

    # -------------------------------------------------
    # دانشجو فقط بازخوردهای خودش را می‌بیند.
    # -------------------------------------------------

    if current_user.role == Roles.STUDENT:

        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به یک دانشجو متصل نیست",
            )

        student_id = current_user.student_id

    # -------------------------------------------------
    # اگر سفر مشخص شده باشد، دسترسی آن بررسی می‌شود.
    # -------------------------------------------------

    if trip_id is not None:

        trip = get_trip(
            db,
            trip_id,
        )

        check_trip_access(
            db,
            current_user,
            trip,
        )

    # -------------------------------------------------
    # اگر دانشجو مشخص شده باشد
    # -------------------------------------------------

    if student_id is not None:

        student = get_student(
            db,
            student_id,
        )

        # شرکت نباید بتواند با student_id به اطلاعات
        # دانشجوی دانشگاه‌های دیگر دسترسی پیدا کند.
        if current_user.role == Roles.COMPANY_ADMIN:

            if trip_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="برای جست‌وجوی بازخورد توسط شرکت، تعیین سفر الزامی است",
                )

            trip = get_trip(
                db,
                trip_id,
            )

            check_trip_company_access(
                db,
                current_user,
                trip,
            )

            if student.university_id != trip.university_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="دانشجو متعلق به دانشگاه این سفر نیست",
                )

        else:

            check_university_access(
                current_user=current_user,
                university_id=student.university_id,
            )

    # -------------------------------------------------
    # دریافت بازخوردها
    # -------------------------------------------------

    feedbacks = get_feedbacks(
        db,
        trip_id=trip_id,
        student_id=student_id,
        feedback_type=feedback_type,
        is_resolved=is_resolved,
    )

    # -------------------------------------------------
    # Super Admin
    # -------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:
        return feedbacks

    # -------------------------------------------------
    # شرکت حمل‌ونقل
    # -------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        filtered_feedbacks = []

        for feedback in feedbacks:

            trip = feedback.trip

            if trip is None:
                continue

            try:

                check_trip_company_access(
                    db,
                    current_user,
                    trip,
                )

                filtered_feedbacks.append(feedback)

            except HTTPException:
                continue

        return filtered_feedbacks

    # -------------------------------------------------
    # کاربران دانشگاه و دانشجو
    # -------------------------------------------------

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست",
        )

    filtered_feedbacks = []

    for feedback in feedbacks:

        trip = feedback.trip

        if trip is None:
            continue

        if trip.university_id != current_user.university_id:
            continue

        if current_user.role == Roles.STUDENT:

            if feedback.student_id != current_user.student_id:
                continue

        filtered_feedbacks.append(feedback)

    return filtered_feedbacks


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
)
def get_feedback_endpoint(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده بازخورد را ندارید",
        )

    feedback = get_feedback(
        db,
        feedback_id,
    )

    trip = get_trip(
        db,
        feedback.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    # -------------------------------------------------
    # دانشجو فقط بازخورد خودش را می‌بیند.
    # -------------------------------------------------

    if current_user.role == Roles.STUDENT:

        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به یک دانشجو متصل نیست",
            )

        if feedback.student_id != current_user.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما به این بازخورد دسترسی ندارید",
            )

    return feedback


@router.patch(
    "/{feedback_id}/resolve",
    response_model=FeedbackResponse,
)
def resolve_feedback_endpoint(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in RESOLVE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز رسیدگی به بازخورد را ندارید",
        )

    feedback = get_feedback(
        db,
        feedback_id,
    )

    trip = get_trip(
        db,
        feedback.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    resolved_feedback = resolve_feedback(
        db,
        feedback_id=feedback_id,
    )

    return resolved_feedback