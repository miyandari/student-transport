from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
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


def get_contract_or_404(
    db: Session,
    contract_id: int,
):
    contract = (
        db.query(Contract)
        .filter(
            Contract.id == contract_id
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
):
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو پیدا نشد",
        )

    return vehicle


def validate_dates(
    start_date: date | None,
    end_date: date | None,
):
    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد",
        )


def check_management_contract_access(
    db: Session,
    current_user: User,
    contract: Contract,
):
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
):
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


@router.post(
    "/",
    response_model=ContractVehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_vehicle(
    data: ContractVehicleCreate,
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

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد غیرفعال است",
        )

    vehicle = get_vehicle_or_404(
        db,
        data.vehicle_id,
    )

    validate_vehicle_for_contract(
        contract,
        vehicle,
    )

    validate_dates(
        data.start_date,
        data.end_date,
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

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment


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
            ContractVehicle.contract_id == contract_id
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
                == current_user.university_id
            )
        )

    if vehicle_id is not None:
        query = query.filter(
            ContractVehicle.vehicle_id == vehicle_id
        )

    if is_active is not None:
        query = query.filter(
            ContractVehicle.is_active == is_active
        )

    return (
        query
        .order_by(ContractVehicle.id.desc())
        .all()
    )


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

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص خودرو پیدا نشد",
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


@router.patch(
    "/{assignment_id}",
    response_model=ContractVehicleResponse,
)
def update_contract_vehicle(
    assignment_id: int,
    data: ContractVehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش تخصیص خودرو را ندارید",
        )

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص خودرو پیدا نشد",
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

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد غیرفعال است",
        )

    vehicle = get_vehicle_or_404(
        db,
        data.vehicle_id,
    )

    validate_vehicle_for_contract(
        contract,
        vehicle,
    )

    validate_dates(
        data.start_date,
        data.end_date,
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

    assignment.vehicle_id = data.vehicle_id
    assignment.start_date = data.start_date
    assignment.end_date = data.end_date
    assignment.is_active = data.is_active

    db.commit()
    db.refresh(assignment)

    return assignment


@router.patch(
    "/{assignment_id}/status",
    response_model=ContractVehicleResponse,
)
def update_contract_vehicle_status(
    assignment_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت تخصیص را ندارید",
        )

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص خودرو پیدا نشد",
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

    assignment.is_active = is_active

    db.commit()
    db.refresh(assignment)

    return assignment