from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.trip import Trip
from app.models.trip_assignment import TripAssignment
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.models.contract_driver import ContractDriver
from app.models.contract_vehicle import ContractVehicle
from app.models.service import Service
from app.models.contract import Contract
from app.models.user import User
from app.schemas.trip_assignment import (
    TripAssignmentCreate,
    TripAssignmentResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_trip_company_access,
)
from app.core.roles import Roles
from app.core.audit_actions import AuditActions
from app.services.trip_assignment_service import (
    activate_assignment,
    deactivate_assignment,
    replace_active_assignment,
)
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/trip-assignments",
    tags=["Trip Assignments"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}

MANAGEMENT_AND_COMPANY_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:

    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} نامعتبر است",
        )


def get_trip_or_404(
    db: Session,
    trip_id: int,
) -> Trip:

    validate_positive_id(
        trip_id,
        "شناسه سفر",
    )

    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id,
        )
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر پیدا نشد",
        )

    return trip


def get_assignment_or_404(
    db: Session,
    assignment_id: int,
) -> TripAssignment:

    validate_positive_id(
        assignment_id,
        "شناسه تخصیص",
    )

    assignment = (
        db.query(TripAssignment)
        .filter(
            TripAssignment.id == assignment_id,
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص پیدا نشد",
        )

    return assignment


def get_trip_contract(
    db: Session,
    trip: Trip,
) -> Contract:

    service = (
        db.query(Service)
        .filter(
            Service.id == trip.service_id,
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس مرتبط با سفر پیدا نشد",
        )

    if service.contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سرویس قرارداد مشخص نشده است",
        )

    contract = (
        db.query(Contract)
        .filter(
            Contract.id == service.contract_id,
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد مرتبط با سرویس پیدا نشد",
        )

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد مرتبط با سفر غیرفعال است",
        )

    if trip.trip_date < contract.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ سفر قبل از شروع قرارداد است",
        )

    if trip.trip_date > contract.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ سفر بعد از پایان قرارداد است",
        )

    if contract.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد مرتبط با سرویس متعلق به دانشگاه این سفر نیست",
        )

    return contract


def validate_contract_assignment_date(
    trip: Trip,
    start_date,
    end_date,
    resource_name: str,
) -> None:

    if (
        start_date is not None
        and trip.trip_date < start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{resource_name} در تاریخ سفر هنوز "
                "اعتبار نداشته است"
            ),
        )

    if (
        end_date is not None
        and trip.trip_date > end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"اعتبار {resource_name} در تاریخ سفر "
                "به پایان رسیده است"
            ),
        )


def validate_driver_for_trip(
    db: Session,
    trip: Trip,
    contract: Contract,
    driver_id: int | None,
) -> None:

    if driver_id is None:
        return

    validate_positive_id(
        driver_id,
        "شناسه راننده",
    )

    driver = (
        db.query(Driver)
        .filter(
            Driver.id == driver_id,
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده پیدا نشد",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده غیرفعال است",
        )

    if driver.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به دانشگاه این سفر نیست",
        )

    if driver.transport_company_id != contract.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به شرکت قرارداد این سفر نیست",
        )

    assignment = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == contract.id,
            ContractDriver.driver_id == driver.id,
            ContractDriver.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده به قرارداد این سفر تخصیص داده نشده است",
        )

    validate_contract_assignment_date(
        trip,
        assignment.start_date,
        assignment.end_date,
        "تخصیص راننده به قرارداد",
    )


def validate_vehicle_for_trip(
    db: Session,
    trip: Trip,
    contract: Contract,
    vehicle_id: int | None,
) -> None:

    if vehicle_id is None:
        return

    validate_positive_id(
        vehicle_id,
        "شناسه خودرو",
    )

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو پیدا نشد",
        )

    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو غیرفعال است",
        )

    if vehicle.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو متعلق به دانشگاه این سفر نیست",
        )

    if vehicle.transport_company_id != contract.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو متعلق به شرکت قرارداد این سفر نیست",
        )

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == contract.id,
            ContractVehicle.vehicle_id == vehicle.id,
            ContractVehicle.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو به قرارداد این سفر تخصیص داده نشده است",
        )

    validate_contract_assignment_date(
        trip,
        assignment.start_date,
        assignment.end_date,
        "تخصیص خودرو به قرارداد",
    )


def validate_assignment_type(
    assignment_type: str,
) -> None:

    if assignment_type not in {
        "primary",
        "substitute",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع تخصیص باید primary یا substitute باشد",
        )


def validate_assignment_dates(
    start_at: datetime | None,
    end_at: datetime | None,
) -> None:

    if (
        start_at is not None
        and end_at is not None
        and end_at < start_at
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان پایان نمی‌تواند قبل از زمان شروع باشد",
        )


def validate_replacement_assignment(
    db: Session,
    trip: Trip,
    replaces_assignment_id: int | None,
    assignment_type: str,
) -> None:

    if replaces_assignment_id is None:
        return

    validate_positive_id(
        replaces_assignment_id,
        "شناسه تخصیص قبلی",
    )

    if assignment_type != "substitute":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط تخصیص جایگزین می‌تواند تخصیص قبلی داشته باشد",
        )

    previous_assignment = (
        db.query(TripAssignment)
        .filter(
            TripAssignment.id == replaces_assignment_id,
        )
        .first()
    )

    if previous_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص جایگزین‌شونده پیدا نشد",
        )

    if previous_assignment.trip_id != trip.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تخصیص قبلی متعلق به این سفر نیست",
        )

    if not previous_assignment.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تخصیص قبلی باید در حال حاضر فعال باشد",
        )


def resolve_replacement_assignment(
    db: Session,
    trip: Trip,
    assignment_type: str,
    requested_replaces_assignment_id: int | None,
) -> int | None:

    if assignment_type != "substitute":

        if requested_replaces_assignment_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای تخصیص اصلی، replaces_assignment_id نباید مشخص شود",
            )

        return None

    current_assignment = (
        db.query(TripAssignment)
        .filter(
            TripAssignment.trip_id == trip.id,
            TripAssignment.is_active.is_(True),
        )
        .order_by(
            TripAssignment.id.desc(),
        )
        .first()
    )

    if current_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای ایجاد تخصیص جایگزین، ابتدا باید یک تخصیص فعال وجود داشته باشد",
        )

    if requested_replaces_assignment_id is not None:

        validate_positive_id(
            requested_replaces_assignment_id,
            "شناسه تخصیص قبلی",
        )

        if (
            requested_replaces_assignment_id
            != current_assignment.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تخصیص جایگزین باید جایگزین تخصیص فعال فعلی باشد",
            )

    return current_assignment.id


def assignment_snapshot(
    assignment: TripAssignment | None,
):

    if assignment is None:
        return None

    return {
        "id": assignment.id,
        "trip_id": assignment.trip_id,
        "driver_id": assignment.driver_id,
        "vehicle_id": assignment.vehicle_id,
        "assignment_type": assignment.assignment_type,
        "replaces_assignment_id": assignment.replaces_assignment_id,
        "reason": assignment.reason,
        "start_at": (
            assignment.start_at.isoformat()
            if assignment.start_at
            else None
        ),
        "end_at": (
            assignment.end_at.isoformat()
            if assignment.end_at
            else None
        ),
        "is_active": assignment.is_active,
    }


@router.post(
    "/",
    response_model=TripAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_assignment(
    data: TripAssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_AND_COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تخصیص راننده یا خودرو به سفر را ندارید",
        )

    trip = get_trip_or_404(
        db,
        data.trip_id,
    )

    check_trip_company_access(
        db,
        current_user,
        trip.id,
    )

    contract = get_trip_contract(
        db,
        trip,
    )

    validate_assignment_type(
        data.assignment_type,
    )

    validate_assignment_dates(
        data.start_at,
        data.end_at,
    )

    validate_driver_for_trip(
        db,
        trip,
        contract,
        data.driver_id,
    )

    validate_vehicle_for_trip(
        db,
        trip,
        contract,
        data.vehicle_id,
    )

    if (
        data.driver_id is None
        and data.vehicle_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل راننده یا خودرو باید مشخص شود",
        )

    replaces_assignment_id = resolve_replacement_assignment(
        db,
        trip,
        data.assignment_type,
        data.replaces_assignment_id,
    )

    if data.assignment_type == "substitute":
        validate_replacement_assignment(
            db,
            trip,
            replaces_assignment_id,
            data.assignment_type,
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        assigned_by_user_id = current_user.id
    else:
        assigned_by_user_id = data.assigned_by_user_id

    assignment = TripAssignment(
        trip_id=data.trip_id,
        driver_id=data.driver_id,
        vehicle_id=data.vehicle_id,
        assigned_by_user_id=assigned_by_user_id,
        replaces_assignment_id=replaces_assignment_id,
        assignment_type=data.assignment_type,
        reason=data.reason,
        start_at=data.start_at,
        end_at=data.end_at,
        is_active=False,
    )

    db.add(assignment)
    db.flush()

    old_assignment = None

    if data.is_active:

        old_assignment = (
            db.query(TripAssignment)
            .filter(
                TripAssignment.trip_id == trip.id,
                TripAssignment.is_active.is_(True),
                TripAssignment.id != assignment.id,
            )
            .first()
        )

        replace_active_assignment(
            db,
            trip,
            assignment,
        )

    create_audit_log(
        db,
        user=current_user,
        action=(
            AuditActions.REPLACE
            if data.assignment_type == "substitute"
            else AuditActions.ASSIGN
        ),
        entity_type="TripAssignment",
        entity_id=assignment.id,
        description=(
            "ایجاد تخصیص جایگزین برای سفر"
            if data.assignment_type == "substitute"
            else "ایجاد تخصیص اصلی برای سفر"
        ),
        old_values=assignment_snapshot(
            old_assignment,
        ),
        new_values=assignment_snapshot(
            assignment,
        ),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        user_agent=request.headers.get(
            "user-agent",
        ),
    )

    try:
        db.commit()
        db.refresh(assignment)
    except Exception:
        db.rollback()
        raise

    return assignment


@router.get(
    "/",
    response_model=list[TripAssignmentResponse],
)
def get_trip_assignments(
    trip_id: int | None = None,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_AND_COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده تخصیص‌ها را ندارید",
        )

    if driver_id is not None:
        validate_positive_id(
            driver_id,
            "شناسه راننده",
        )

    if vehicle_id is not None:
        validate_positive_id(
            vehicle_id,
            "شناسه خودرو",
        )

    query = db.query(TripAssignment)

    if trip_id is not None:

        trip = get_trip_or_404(
            db,
            trip_id,
        )

        check_trip_company_access(
            db,
            current_user,
            trip.id,
        )

        query = query.filter(
            TripAssignment.trip_id == trip_id,
        )

    elif current_user.role == Roles.COMPANY_ADMIN:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای شرکت حمل‌ونقل، تعیین trip_id الزامی است",
        )

    elif current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = (
            query
            .join(
                Trip,
                Trip.id == TripAssignment.trip_id,
            )
            .filter(
                Trip.university_id
                == current_user.university_id,
            )
        )

    if driver_id is not None:
        query = query.filter(
            TripAssignment.driver_id == driver_id,
        )

    if vehicle_id is not None:
        query = query.filter(
            TripAssignment.vehicle_id == vehicle_id,
        )

    if is_active is not None:
        query = query.filter(
            TripAssignment.is_active == is_active,
        )

    return (
        query
        .order_by(
            TripAssignment.id.desc(),
        )
        .all()
    )


@router.get(
    "/{assignment_id}",
    response_model=TripAssignmentResponse,
)
def get_trip_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_AND_COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این تخصیص را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    trip = get_trip_or_404(
        db,
        assignment.trip_id,
    )

    check_trip_company_access(
        db,
        current_user,
        trip.id,
    )

    return assignment


@router.patch(
    "/{assignment_id}",
    response_model=TripAssignmentResponse,
)
def update_trip_assignment(
    assignment_id: int,
    data: TripAssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_AND_COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش تخصیص را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    trip = get_trip_or_404(
        db,
        assignment.trip_id,
    )

    check_trip_company_access(
        db,
        current_user,
        trip.id,
    )

    old_values = assignment_snapshot(
        assignment,
    )

    if data.trip_id != assignment.trip_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تغییر سفر تخصیص از این بخش امکان‌پذیر نیست",
        )

    contract = get_trip_contract(
        db,
        trip,
    )

    validate_assignment_type(
        data.assignment_type,
    )

    validate_assignment_dates(
        data.start_at,
        data.end_at,
    )

    validate_driver_for_trip(
        db,
        trip,
        contract,
        data.driver_id,
    )

    validate_vehicle_for_trip(
        db,
        trip,
        contract,
        data.vehicle_id,
    )

    if (
        data.driver_id is None
        and data.vehicle_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل راننده یا خودرو باید مشخص شود",
        )

    if data.assignment_type == "primary":

        if data.replaces_assignment_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای تخصیص اصلی، replaces_assignment_id نباید مشخص شود",
            )

        assignment.replaces_assignment_id = None

    else:

        current_assignment = (
            db.query(TripAssignment)
            .filter(
                TripAssignment.trip_id == trip.id,
                TripAssignment.is_active.is_(True),
                TripAssignment.id != assignment.id,
            )
            .order_by(
                TripAssignment.id.desc(),
            )
            .first()
        )

        if current_assignment is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای تخصیص جایگزین باید یک تخصیص فعال وجود داشته باشد",
            )

        if (
            data.replaces_assignment_id is not None
            and data.replaces_assignment_id
            != current_assignment.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تخصیص جایگزین باید جایگزین تخصیص فعال فعلی باشد",
            )

        assignment.replaces_assignment_id = (
            current_assignment.id
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        assignment.assigned_by_user_id = current_user.id
    else:
        assignment.assigned_by_user_id = data.assigned_by_user_id

    assignment.driver_id = data.driver_id
    assignment.vehicle_id = data.vehicle_id
    assignment.assignment_type = data.assignment_type
    assignment.reason = data.reason
    assignment.start_at = data.start_at
    assignment.end_at = data.end_at

    db.flush()

    if data.is_active:
        replace_active_assignment(
            db,
            trip,
            assignment,
        )
    else:
        assignment.is_active = False

    create_audit_log(
        db,
        user=current_user,
        action=(
            AuditActions.REPLACE
            if assignment.assignment_type == "substitute"
            else AuditActions.UPDATE
        ),
        entity_type="TripAssignment",
        entity_id=assignment.id,
        description="ویرایش تخصیص سفر",
        old_values=old_values,
        new_values=assignment_snapshot(
            assignment,
        ),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        user_agent=request.headers.get(
            "user-agent",
        ),
    )

    try:
        db.commit()
        db.refresh(assignment)
    except Exception:
        db.rollback()
        raise

    return assignment


@router.patch(
    "/{assignment_id}/status",
    response_model=TripAssignmentResponse,
)
def update_trip_assignment_status(
    assignment_id: int,
    is_active: bool,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_AND_COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت تخصیص را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    trip = get_trip_or_404(
        db,
        assignment.trip_id,
    )

    check_trip_company_access(
        db,
        current_user,
        trip.id,
    )

    old_values = assignment_snapshot(
        assignment,
    )

    if is_active:

        contract = get_trip_contract(
            db,
            trip,
        )

        validate_driver_for_trip(
            db,
            trip,
            contract,
            assignment.driver_id,
        )

        validate_vehicle_for_trip(
            db,
            trip,
            contract,
            assignment.vehicle_id,
        )

        activate_assignment(
            db,
            assignment,
        )

        action = AuditActions.ACTIVATE
        description = "فعال‌سازی تخصیص سفر"

    else:

        deactivate_assignment(
            db,
            assignment,
        )

        action = AuditActions.DEACTIVATE
        description = "غیرفعال‌سازی تخصیص سفر"

    create_audit_log(
        db,
        user=current_user,
        action=action,
        entity_type="TripAssignment",
        entity_id=assignment.id,
        description=description,
        old_values=old_values,
        new_values=assignment_snapshot(
            assignment,
        ),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        user_agent=request.headers.get(
            "user-agent",
        ),
    )

    try:
        db.commit()
        db.refresh(assignment)
    except Exception:
        db.rollback()
        raise

    return assignment