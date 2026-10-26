from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contract import Contract
from app.models.contract_vehicle import ContractVehicle
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.contract_vehicle import (
    ContractVehicleCreate,
    ContractVehicleResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_contract_access,
)
from app.core.roles import Roles
from app.core.audit_actions import AuditActions
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/contract-vehicles",
    tags=["Contract Vehicles"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
}

VIEW_ROLES = MANAGEMENT_ROLES


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:

    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} نامعتبر است",
        )


def get_contract_or_404(
    db: Session,
    contract_id: int,
) -> Contract:

    validate_positive_id(
        contract_id,
        "شناسه قرارداد",
    )

    contract = (
        db.query(Contract)
        .filter(
            Contract.id == contract_id,
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="قرارداد پیدا نشد",
        )

    return contract


def get_vehicle_or_404(
    db: Session,
    vehicle_id: int,
) -> Vehicle:

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

    return vehicle


def get_assignment_or_404(
    db: Session,
    assignment_id: int,
) -> ContractVehicle:

    validate_positive_id(
        assignment_id,
        "شناسه تخصیص",
    )

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.id == assignment_id,
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص خودرو پیدا نشد",
        )

    return assignment


def validate_dates(
    start_date: date | None,
    end_date: date | None,
) -> None:

    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد",
        )


def validate_assignment_dates_against_contract(
    contract: Contract,
    start_date: date | None,
    end_date: date | None,
) -> None:

    validate_dates(
        start_date,
        end_date,
    )

    if (
        start_date is not None
        and start_date < contract.start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ شروع تخصیص نمی‌تواند قبل از شروع قرارداد باشد",
        )

    if (
        end_date is not None
        and end_date > contract.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان تخصیص نمی‌تواند بعد از پایان قرارداد باشد",
        )


def check_management_contract_access(
    db: Session,
    current_user: User,
    contract: Contract,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب شرکت به شرکت حمل‌ونقل متصل نیست",
            )

        check_contract_access(
            db,
            current_user,
            contract.id,
        )

        return

    if current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        if current_user.university_id != contract.university_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما به این قرارداد دسترسی ندارید",
            )


def validate_vehicle_for_contract(
    contract: Contract,
    vehicle: Vehicle,
) -> None:

    if vehicle.university_id != contract.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو متعلق به دانشگاه این قرارداد نیست",
        )

    if vehicle.transport_company_id != contract.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو متعلق به شرکت این قرارداد نیست",
        )

    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودروی انتخاب‌شده غیرفعال است",
        )


def assignment_snapshot(
    assignment: ContractVehicle | None,
):
    if assignment is None:
        return None

    return {
        "id": assignment.id,
        "contract_id": assignment.contract_id,
        "vehicle_id": assignment.vehicle_id,
        "start_date": (
            assignment.start_date.isoformat()
            if assignment.start_date
            else None
        ),
        "end_date": (
            assignment.end_date.isoformat()
            if assignment.end_date
            else None
        ),
        "is_active": assignment.is_active,
    }


def validate_active_assignment(
    contract: Contract,
    vehicle: Vehicle,
    start_date: date | None,
    end_date: date | None,
) -> None:

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد غیرفعال است",
        )

    validate_vehicle_for_contract(
        contract,
        vehicle,
    )

    validate_assignment_dates_against_contract(
        contract,
        start_date,
        end_date,
    )


# =========================================================
# ایجاد تخصیص خودرو به قرارداد
# =========================================================

@router.post(
    "/",
    response_model=ContractVehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_vehicle(
    data: ContractVehicleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تخصیص خودرو به قرارداد را ندارید",
        )

    contract = get_contract_or_404(
        db,
        data.contract_id,
    )

    check_management_contract_access(
        db,
        current_user,
        contract,
    )

    vehicle = get_vehicle_or_404(
        db,
        data.vehicle_id,
    )

    validate_vehicle_for_contract(
        contract,
        vehicle,
    )

    validate_assignment_dates_against_contract(
        contract,
        data.start_date,
        data.end_date,
    )

    if data.is_active and not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای قرارداد غیرفعال نمی‌توان تخصیص فعال ایجاد کرد",
        )

    existing = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == data.contract_id,
            ContractVehicle.vehicle_id == data.vehicle_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این خودرو قبلاً به این قرارداد تخصیص داده شده است",
        )

    assignment = ContractVehicle(
        contract_id=data.contract_id,
        vehicle_id=data.vehicle_id,
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=data.is_active,
    )

    try:
        db.add(assignment)
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=AuditActions.ASSIGN,
            entity_type="ContractVehicle",
            entity_id=assignment.id,
            description="تخصیص خودرو به قرارداد",
            old_values=None,
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

        db.commit()
        db.refresh(assignment)

    except Exception:
        db.rollback()
        raise

    return assignment


# =========================================================
# فهرست خودروهای یک قرارداد
# =========================================================

@router.get(
    "/",
    response_model=list[ContractVehicleResponse],
)
def get_contract_vehicles(
    contract_id: int | None = None,
    vehicle_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده تخصیص خودروها را ندارید",
        )

    if vehicle_id is not None:
        validate_positive_id(
            vehicle_id,
            "شناسه خودرو",
        )

    query = db.query(ContractVehicle)

    if contract_id is not None:

        contract = get_contract_or_404(
            db,
            contract_id,
        )

        check_management_contract_access(
            db,
            current_user,
            contract,
        )

        query = query.filter(
            ContractVehicle.contract_id == contract_id,
        )

    elif current_user.role == Roles.COMPANY_ADMIN:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای شرکت حمل‌ونقل، تعیین contract_id الزامی است",
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
                Contract,
                Contract.id == ContractVehicle.contract_id,
            )
            .filter(
                Contract.university_id
                == current_user.university_id,
            )
        )

    if vehicle_id is not None:
        query = query.filter(
            ContractVehicle.vehicle_id == vehicle_id,
        )

    if is_active is not None:
        query = query.filter(
            ContractVehicle.is_active == is_active,
        )

    return (
        query
        .order_by(
            ContractVehicle.id.desc(),
        )
        .all()
    )


# =========================================================
# مشاهده یک تخصیص
# =========================================================

@router.get(
    "/{assignment_id}",
    response_model=ContractVehicleResponse,
)
def get_contract_vehicle(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این تخصیص را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    contract = get_contract_or_404(
        db,
        assignment.contract_id,
    )

    check_management_contract_access(
        db,
        current_user,
        contract,
    )

    return assignment


# =========================================================
# ویرایش تخصیص
# =========================================================

@router.patch(
    "/{assignment_id}",
    response_model=ContractVehicleResponse,
)
def update_contract_vehicle(
    assignment_id: int,
    data: ContractVehicleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش تخصیص خودرو را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    contract = get_contract_or_404(
        db,
        assignment.contract_id,
    )

    check_management_contract_access(
        db,
        current_user,
        contract,
    )

    if data.contract_id != assignment.contract_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تغییر قرارداد تخصیص از این بخش امکان‌پذیر نیست",
        )

    vehicle = get_vehicle_or_404(
        db,
        data.vehicle_id,
    )

    validate_vehicle_for_contract(
        contract,
        vehicle,
    )

    validate_assignment_dates_against_contract(
        contract,
        data.start_date,
        data.end_date,
    )

    if data.is_active and not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای قرارداد غیرفعال نمی‌توان تخصیص فعال داشت",
        )

    duplicate = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == data.contract_id,
            ContractVehicle.vehicle_id == data.vehicle_id,
            ContractVehicle.id != assignment.id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این خودرو قبلاً به این قرارداد تخصیص داده شده است",
        )

    old_values = assignment_snapshot(
        assignment,
    )

    assignment.vehicle_id = data.vehicle_id
    assignment.start_date = data.start_date
    assignment.end_date = data.end_date
    assignment.is_active = data.is_active

    try:
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=AuditActions.UPDATE,
            entity_type="ContractVehicle",
            entity_id=assignment.id,
            description="ویرایش تخصیص خودرو به قرارداد",
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

        db.commit()
        db.refresh(assignment)

    except Exception:
        db.rollback()
        raise

    return assignment


# =========================================================
# تغییر وضعیت تخصیص
# =========================================================

@router.patch(
    "/{assignment_id}/status",
    response_model=ContractVehicleResponse,
)
def update_contract_vehicle_status(
    assignment_id: int,
    is_active: bool,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت تخصیص را ندارید",
        )

    assignment = get_assignment_or_404(
        db,
        assignment_id,
    )

    contract = get_contract_or_404(
        db,
        assignment.contract_id,
    )

    check_management_contract_access(
        db,
        current_user,
        contract,
    )

    old_values = assignment_snapshot(
        assignment,
    )

    if is_active:

        vehicle = get_vehicle_or_404(
            db,
            assignment.vehicle_id,
        )

        validate_active_assignment(
            contract,
            vehicle,
            assignment.start_date,
            assignment.end_date,
        )

        action = AuditActions.ACTIVATE
        description = "فعال‌سازی تخصیص خودرو به قرارداد"

    else:

        action = AuditActions.DEACTIVATE
        description = "غیرفعال‌سازی تخصیص خودرو از قرارداد"

    assignment.is_active = is_active

    try:
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=action,
            entity_type="ContractVehicle",
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

        db.commit()
        db.refresh(assignment)

    except Exception:
        db.rollback()
        raise

    return assignment