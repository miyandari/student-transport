from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contract import Contract
from app.models.contract_driver import ContractDriver
from app.models.contract_vehicle import ContractVehicle
from app.models.transport_company import TransportCompany
from app.models.university import University
from app.models.user import User
from app.schemas.contract import (
    ContractCreate,
    ContractResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_contract_access,
)
from app.core.roles import Roles


router = APIRouter(
    prefix="/contracts",
    tags=["Contracts"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}

VIEW_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


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
            detail="دانشگاه موردنظر پیدا نشد",
        )

    if not university.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه موردنظر غیرفعال است",
        )

    return university


def get_active_transport_company(
    db: Session,
    transport_company_id: int,
):
    company = (
        db.query(TransportCompany)
        .filter(
            TransportCompany.id == transport_company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="شرکت حمل‌ونقل موردنظر پیدا نشد",
        )

    if not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شرکت حمل‌ونقل موردنظر غیرفعال است",
        )

    return company


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
            detail="قرارداد موردنظر پیدا نشد",
        )

    return contract


def check_contract_resource_access(
    db: Session,
    current_user: User,
    contract: Contract,
):
    """
    کنترل دسترسی به قرارداد:

    - super_admin: همه قراردادها
    - company_admin: فقط قراردادهای شرکت خودش
    - سایر کاربران مدیریتی: فقط قراردادهای دانشگاه خودشان
    """

    check_contract_access(
        db,
        current_user,
        contract.id,
    )


def check_active_assignments_before_company_change(
    db: Session,
    contract: Contract,
    new_transport_company_id: int,
):
    """
    در صورت وجود تخصیص فعال راننده یا خودرو،
    امکان تغییر شرکت قرارداد وجود ندارد.
    """

    if new_transport_company_id == contract.transport_company_id:
        return

    active_driver_assignments = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == contract.id,
            ContractDriver.is_active.is_(True),
        )
        .count()
    )

    active_vehicle_assignments = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == contract.id,
            ContractVehicle.is_active.is_(True),
        )
        .count()
    )

    if (
        active_driver_assignments > 0
        or active_vehicle_assignments > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "تا زمانی که تخصیص‌های فعال راننده یا خودرو وجود دارد، "
                "امکان تغییر شرکت قرارداد وجود ندارد"
            ),
        )


# =========================================================
# ایجاد قرارداد
# =========================================================

@router.post(
    "/",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract(
    contract_data: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد قرارداد را ندارید",
        )

    check_university_access(
        current_user,
        contract_data.university_id,
    )

    get_active_university(
        db,
        contract_data.university_id,
    )

    contract_number = normalize_text(
        contract_data.contract_number
    )

    description = normalize_text(
        contract_data.description
    )

    if not contract_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره قرارداد نمی‌تواند خالی باشد",
        )

    if contract_data.end_date < contract_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان قرارداد نمی‌تواند قبل از تاریخ شروع باشد",
        )

    existing_contract = (
        db.query(Contract)
        .filter(
            Contract.contract_number == contract_number
        )
        .first()
    )

    if existing_contract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این شماره قرارداد قبلاً ثبت شده است",
        )

    get_active_transport_company(
        db,
        contract_data.transport_company_id,
    )

    contract = Contract(
        university_id=contract_data.university_id,
        transport_company_id=contract_data.transport_company_id,
        contract_number=contract_number,
        start_date=contract_data.start_date,
        end_date=contract_data.end_date,
        contract_amount=contract_data.contract_amount,
        description=description,
        is_active=contract_data.is_active,
    )

    db.add(contract)
    db.commit()
    db.refresh(contract)

    return contract


# =========================================================
# دریافت فهرست قراردادها
# =========================================================

@router.get(
    "/",
    response_model=list[ContractResponse],
)
def get_contracts(
    university_id: int | None = None,
    transport_company_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده قراردادها را ندارید",
        )

    query = db.query(Contract)

    # -----------------------------------------------------
    # شرکت حمل‌ونقل
    # -----------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب شرکت به شرکت حمل‌ونقل متصل نیست",
            )

        query = query.filter(
            Contract.transport_company_id
            == current_user.transport_company_id
        )

        if university_id is not None:
            query = query.filter(
                Contract.university_id == university_id
            )

        if is_active is not None:
            query = query.filter(
                Contract.is_active == is_active
            )

        return (
            query
            .order_by(Contract.id.desc())
            .all()
        )

    # -----------------------------------------------------
    # مدیریت دانشگاه
    # -----------------------------------------------------

    if current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Contract.university_id
            == current_user.university_id
        )

    elif university_id is not None:

        query = query.filter(
            Contract.university_id
            == university_id
        )

    if transport_company_id is not None:
        query = query.filter(
            Contract.transport_company_id
            == transport_company_id
        )

    if is_active is not None:
        query = query.filter(
            Contract.is_active
            == is_active
        )

    return (
        query
        .order_by(Contract.id.desc())
        .all()
    )


# =========================================================
# مشاهده یک قرارداد
# =========================================================

@router.get(
    "/{contract_id}",
    response_model=ContractResponse,
)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده قراردادها را ندارید",
        )

    contract = get_contract_or_404(
        db,
        contract_id,
    )

    check_contract_resource_access(
        db,
        current_user,
        contract,
    )

    return contract


# =========================================================
# ویرایش قرارداد
# =========================================================

@router.patch(
    "/{contract_id}",
    response_model=ContractResponse,
)
def update_contract(
    contract_id: int,
    contract_data: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش قرارداد را ندارید",
        )

    contract = get_contract_or_404(
        db,
        contract_id,
    )

    check_university_access(
        current_user,
        contract.university_id,
    )

    if contract_data.university_id != contract.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه قرارداد از این بخش وجود ندارد",
        )

    get_active_university(
        db,
        contract.university_id,
    )

    contract_number = normalize_text(
        contract_data.contract_number
    )

    description = normalize_text(
        contract_data.description
    )

    if not contract_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره قرارداد نمی‌تواند خالی باشد",
        )

    if contract_data.end_date < contract_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان قرارداد نمی‌تواند قبل از تاریخ شروع باشد",
        )

    existing_contract = (
        db.query(Contract)
        .filter(
            Contract.contract_number == contract_number,
            Contract.id != contract.id,
        )
        .first()
    )

    if existing_contract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این شماره قرارداد قبلاً ثبت شده است",
        )

    check_active_assignments_before_company_change(
        db,
        contract,
        contract_data.transport_company_id,
    )

    get_active_transport_company(
        db,
        contract_data.transport_company_id,
    )

    contract.transport_company_id = (
        contract_data.transport_company_id
    )
    contract.contract_number = contract_number
    contract.start_date = contract_data.start_date
    contract.end_date = contract_data.end_date
    contract.contract_amount = contract_data.contract_amount
    contract.description = description
    contract.is_active = contract_data.is_active

    db.commit()
    db.refresh(contract)

    return contract


# =========================================================
# تغییر وضعیت قرارداد
# =========================================================

@router.patch(
    "/{contract_id}/status",
    response_model=ContractResponse,
)
def update_contract_status(
    contract_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت قرارداد را ندارید",
        )

    contract = get_contract_or_404(
        db,
        contract_id,
    )

    check_university_access(
        current_user,
        contract.university_id,
    )

    contract.is_active = is_active

    db.commit()
    db.refresh(contract)

    return contract