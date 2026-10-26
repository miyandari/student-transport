
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contract import Contract
from app.models.contract_driver import ContractDriver
from app.models.driver import Driver
from app.models.user import User
from app.schemas.contract_driver import (
    ContractDriverCreate,
    ContractDriverResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_contract_access,
)
from app.core.roles import Roles


router = APIRouter(
    prefix="/contract-drivers",
    tags=["Contract Drivers"],
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


def get_driver_or_404(
    db: Session,
    driver_id: int,
):
    driver = (
        db.query(Driver)
        .filter(
            Driver.id == driver_id
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده پیدا نشد",
        )

    return driver


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


def validate_driver_for_contract(
    contract: Contract,
    driver: Driver,
):
    if driver.university_id != contract.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به دانشگاه این قرارداد نیست",
        )

    if driver.transport_company_id != contract.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به شرکت این قرارداد نیست",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده انتخاب‌شده غیرفعال است",
        )


# =========================================================
# ایجاد تخصیص راننده به قرارداد
# =========================================================

@router.post(
    "/",
    response_model=ContractDriverResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_driver(
    data: ContractDriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تخصیص راننده به قرارداد را ندارید",
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

    driver = get_driver_or_404(
        db,
        data.driver_id,
    )

    validate_driver_for_contract(
        contract,
        driver,
    )

    validate_dates(
        data.start_date,
        data.end_date,
    )

    existing = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == data.contract_id,
            ContractDriver.driver_id == data.driver_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این راننده قبلاً به این قرارداد تخصیص داده شده است",
        )

    assignment = ContractDriver(
        contract_id=data.contract_id,
        driver_id=data.driver_id,
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=data.is_active,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment


# =========================================================
# فهرست رانندگان یک قرارداد
# =========================================================

@router.get(
    "/",
    response_model=list[ContractDriverResponse],
)
def get_contract_drivers(
    contract_id: int | None = None,
    driver_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده تخصیص رانندگان را ندارید",
        )

    query = db.query(ContractDriver)

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
            ContractDriver.contract_id == contract_id
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
                Contract.id == ContractDriver.contract_id,
            )
            .filter(
                Contract.university_id
                == current_user.university_id
            )
        )

    if driver_id is not None:
        query = query.filter(
            ContractDriver.driver_id == driver_id
        )

    if is_active is not None:
        query = query.filter(
            ContractDriver.is_active == is_active
        )

    return (
        query
        .order_by(
            ContractDriver.id.desc()
        )
        .all()
    )


# =========================================================
# مشاهده یک تخصیص
# =========================================================

@router.get(
    "/{assignment_id}",
    response_model=ContractDriverResponse,
)
def get_contract_driver(
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
        db.query(ContractDriver)
        .filter(
            ContractDriver.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص راننده پیدا نشد",
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
    response_model=ContractDriverResponse,
)
def update_contract_driver(
    assignment_id: int,
    data: ContractDriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش تخصیص راننده را ندارید",
        )

    assignment = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص راننده پیدا نشد",
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

    driver = get_driver_or_404(
        db,
        data.driver_id,
    )

    validate_driver_for_contract(
        contract,
        driver,
    )

    validate_dates(
        data.start_date,
        data.end_date,
    )

    duplicate = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == data.contract_id,
            ContractDriver.driver_id == data.driver_id,
            ContractDriver.id != assignment.id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این راننده قبلاً به این قرارداد تخصیص داده شده است",
        )

    assignment.driver_id = data.driver_id
    assignment.start_date = data.start_date
    assignment.end_date = data.end_date
    assignment.is_active = data.is_active

    db.commit()
    db.refresh(assignment)

    return assignment


# =========================================================
# تغییر وضعیت تخصیص
# =========================================================

@router.patch(
    "/{assignment_id}/status",
    response_model=ContractDriverResponse,
)
def update_contract_driver_status(
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
        db.query(ContractDriver)
        .filter(
            ContractDriver.id == assignment_id
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="تخصیص راننده پیدا نشد",
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
