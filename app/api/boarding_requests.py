from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.boarding_request import BoardingRequest
from app.models.trip import Trip
from app.models.user import User
from app.schemas.boarding_request import (
    BoardingRequestCreate,
    BoardingRequestDecision,
    BoardingRequestResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_trip_company_access,
)
from app.core.roles import (
    Roles,
    TRIP_VIEW_ROLES,
)
from app.services.boarding_request_service import (
    approve_boarding_request,
    cancel_boarding_request,
    create_boarding_request,
    get_pending_boarding_requests,
    reject_boarding_request,
)


router = APIRouter(
    prefix="/boarding-requests",
    tags=["Boarding Requests"],
)


def get_trip_or_404(
    db: Session,
    trip_id: int,
) -> Trip:
    if trip_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سفر باید بزرگ‌تر از صفر باشد.",
        )

    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد.",
        )

    return trip


def get_request_or_404(
    db: Session,
    request_id: int,
) -> BoardingRequest:
    if request_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه درخواست نامعتبر است.",
        )

    request = (
        db.query(BoardingRequest)
        .filter(BoardingRequest.id == request_id)
        .first()
    )

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="درخواست سوارشدن پیدا نشد.",
        )

    return request


def check_trip_access(
    db: Session,
    current_user: User,
    trip: Trip,
) -> None:
    if current_user.role == Roles.COMPANY_ADMIN:
        check_trip_company_access(
            db,
            current_user,
            trip,
        )
        return

    check_university_access(
        current_user=current_user,
        university_id=trip.university_id,
    )


def check_driver_trip_access(
    current_user: User,
    trip: Trip,
) -> None:
    if current_user.role != Roles.DRIVER:
        return

    if current_user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب راننده به یک راننده متصل نیست.",
        )

    if trip.driver_id != current_user.driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است.",
        )


def check_driver_or_management_access(
    current_user: User,
) -> None:
    allowed_roles = set(TRIP_VIEW_ROLES) | {
        Roles.COMPANY_ADMIN,
        Roles.DRIVER,
    }

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت درخواست‌های سوارشدن را ندارید.",
        )


# =========================================================
# Student: Create Boarding Request
# =========================================================

@router.post(
    "/",
    response_model=BoardingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_boarding_request_endpoint(
    request_data: BoardingRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != Roles.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط دانشجو می‌تواند درخواست سوارشدن ثبت کند.",
        )

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب دانشجو به یک دانشجو متصل نیست.",
        )

    request = create_boarding_request(
        db=db,
        student_id=current_user.student_id,
        trip_id=request_data.trip_id,
        boarding_station_id=request_data.boarding_station_id,
        is_standing=request_data.is_standing,
        requires_driver_approval=False,
    )

    return request


# =========================================================
# Student: Scan Station QR and Create Boarding Request
# =========================================================

@router.post(
    "/scan",
    response_model=BoardingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def scan_station_qr_endpoint(
    request_data: BoardingRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != Roles.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط دانشجو می‌تواند از طریق QR درخواست سوارشدن ثبت کند.",
        )

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب دانشجو به یک دانشجو متصل نیست.",
        )

    if request_data.boarding_station_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه ایستگاه QR الزامی است.",
        )

    request = create_boarding_request(
        db=db,
        student_id=current_user.student_id,
        trip_id=request_data.trip_id,
        boarding_station_id=request_data.boarding_station_id,
        is_standing=request_data.is_standing,
        requires_driver_approval=True,
    )

    return request


# =========================================================
# Driver / Management: Get Pending Requests
# =========================================================

@router.get(
    "/trip/{trip_id}",
    response_model=list[BoardingRequestResponse],
)
def get_pending_requests_endpoint(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_driver_or_management_access(
        current_user,
    )

    trip = get_trip_or_404(
        db,
        trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    return get_pending_boarding_requests(
        db=db,
        trip_id=trip_id,
    )


# =========================================================
# Driver / Management: Approve Request
# =========================================================

@router.post(
    "/{request_id}/approve",
    response_model=BoardingRequestResponse,
)
def approve_boarding_request_endpoint(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_driver_or_management_access(
        current_user,
    )

    request = get_request_or_404(
        db,
        request_id,
    )

    trip = get_trip_or_404(
        db,
        request.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    return approve_boarding_request(
        db=db,
        request_id=request_id,
        responded_by_user_id=current_user.id,
    )


# =========================================================
# Driver / Management: Reject Request
# =========================================================

@router.post(
    "/{request_id}/reject",
    response_model=BoardingRequestResponse,
)
def reject_boarding_request_endpoint(
    request_id: int,
    decision: BoardingRequestDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_driver_or_management_access(
        current_user,
    )

    request = get_request_or_404(
        db,
        request_id,
    )

    trip = get_trip_or_404(
        db,
        request.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    return reject_boarding_request(
        db=db,
        request_id=request_id,
        responded_by_user_id=current_user.id,
        rejection_reason=decision.rejection_reason,
    )


# =========================================================
# Student: Cancel Request
# =========================================================

@router.post(
    "/{request_id}/cancel",
    response_model=BoardingRequestResponse,
)
def cancel_boarding_request_endpoint(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != Roles.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط دانشجو می‌تواند درخواست خود را لغو کند.",
        )

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب دانشجو به یک دانشجو متصل نیست.",
        )

    return cancel_boarding_request(
        db=db,
        request_id=request_id,
        student_id=current_user.student_id,
    )