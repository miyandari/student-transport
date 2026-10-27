from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.core.audit_actions import AuditActions
from app.services.audit_service import create_audit_log


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


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:

    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} نامعتبر است",
        )


def get_active_university(
    db: Session,
    university_id: int,
):
    validate_positive_id(
        university_id,
        "شناسه دانشگاه",
    )

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
    validate_positive_id(
        transport_company_id,
        "شناسه شرکت حمل‌ونقل",
    )

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
    validate_positive_id(
        contract_id,
        "شناسه قرارداد",
    )

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


def contract_snapshot(
    contract: Contract | None,
):
    if contract is None:
        return None

    return {
        "id": contract.id,
        "university_id": contract.university_id,
        "transport_company_id": contract.transport_company_id,
        "contract_number": contract.contract_number,
        "start_date": (
            contract.start_date.isoformat()
            if contract.start_date
            else None
        ),
        "end_date": (
            contract.end_date.isoformat()
            if contract.end_date
            else None
        ),
        "contract_amount": (
            float(contract.contract_amount)
            if contract.contract_amount is not None
            else None
        ),
        "description": contract.description,
        "is_active": contract.is_active,
    }


def validate_contract_dates(
    start_date,
    end_date,
) -> None:

    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان قرارداد نمی‌تواند قبل از تاریخ شروع باشد",
        )


def validate_active_assignments_against_contract_dates(
    db: Session,
    contract: Contract,
    new_start_date,
    new_end_date,
) -> None:
    """
    بررسی می‌کند که تخصیص‌های فعال راننده و خودرو
    همچنان داخل بازه جدید قرارداد قرار داشته باشند.
    """

    active_driver_assignments = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == contract.id,
            ContractDriver.is_active.is_(True),
        )
        .all()
    )

    for assignment in active_driver_assignments:

        if (
            assignment.start_date is not None
            and assignment.start_date < new_start_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "تاریخ شروع جدید قرارداد با یکی از "
                    "تخصیص‌های فعال رانندگان سازگار نیست"
                ),
            )

        if (
            assignment.end_date is not None
            and assignment.end_date > new_end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "تاریخ پایان جدید قرارداد با یکی از "
                    "تخصیص‌های فعال رانندگان سازگار نیست"
                ),
            )

    active_vehicle_assignments = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == contract.id,
            ContractVehicle.is_active.is_(True),
        )
        .all()
    )

    for assignment in active_vehicle_assignments:

        if (
            assignment.start_date is not None
            and assignment.start_date < new_start_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "تاریخ شروع جدید قرارداد با یکی از "
                    "تخصیص‌های فعال خودروها سازگار نیست"
                ),
            )

        if (
            assignment.end_date is not None
            and assignment.end_date > new_end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "تاریخ پایان جدید قرارداد با یکی از "
                    "تخصیص‌های فعال خودروها سازگار نیست"
                ),
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


def check_active_assignments_before_deactivation(
    db: Session,
    contract: Contract,
) -> None:
    """
    جلوگیری از غیرفعال‌کردن قراردادی که هنوز
    تخصیص فعال راننده یا خودرو دارد.
    """

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
                "ابتدا باید تخصیص‌های فعال رانندگان و خودروهای "
                "این قرارداد غیرفعال شوند"
            ),
        )


def validate_contract_activation(
    db: Session,
    contract: Contract,
) -> None:

    get_active_university(
        db,
        contract.university_id,
    )

    get_active_transport_company(
        db,
        contract.transport_company_id,
    )

    validate_contract_dates(
        contract.start_date,
        contract.end_date,
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
    request: Request,
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

    validate_positive_id(
        contract_data.transport_company_id,
        "شناسه شرکت حمل‌ونقل",
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

    validate_contract_dates(
        contract_data.start_date,
        contract_data.end_date,
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

    if contract_data.is_active:
        get_active_university(
            db,
            contract_data.university_id,
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

    try:
        db.add(contract)
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=AuditActions.CREATE,
            entity_type="Contract",
            entity_id=contract.id,
            description="ایجاد قرارداد",
            old_values=None,
            new_values=contract_snapshot(
                contract,
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
        db.refresh(contract)

    except Exception:
        db.rollback()
        raise

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

    if university_id is not None:
        validate_positive_id(
            university_id,
            "شناسه دانشگاه",
        )

    if transport_company_id is not None:
        validate_positive_id(
            transport_company_id,
            "شناسه شرکت حمل‌ونقل",
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
    request: Request,
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

    validate_contract_dates(
        contract_data.start_date,
        contract_data.end_date,
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

    if (
        contract.start_date != contract_data.start_date
        or contract.end_date != contract_data.end_date
    ):
        validate_active_assignments_against_contract_dates(
            db,
            contract,
            contract_data.start_date,
            contract_data.end_date,
        )

    get_active_transport_company(
        db,
        contract_data.transport_company_id,
    )

    if contract_data.is_active:
        get_active_university(
            db,
            contract.university_id,
        )

        get_active_transport_company(
            db,
            contract_data.transport_company_id,
        )

    elif contract.is_active and not contract_data.is_active:
        check_active_assignments_before_deactivation(
            db,
            contract,
        )

    old_values = contract_snapshot(
        contract,
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

    try:
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=AuditActions.UPDATE,
            entity_type="Contract",
            entity_id=contract.id,
            description="ویرایش قرارداد",
            old_values=old_values,
            new_values=contract_snapshot(
                contract,
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
        db.refresh(contract)

    except Exception:
        db.rollback()
        raise

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
    request: Request,
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

    if is_active:

        validate_contract_activation(
            db,
            contract,
        )

        action = AuditActions.ACTIVATE
        description = "فعال‌سازی قرارداد"

    else:

        if contract.is_active:
            check_active_assignments_before_deactivation(
                db,
                contract,
            )

        action = AuditActions.DEACTIVATE
        description = "غیرفعال‌سازی قرارداد"

    old_values = contract_snapshot(
        contract,
    )

    contract.is_active = is_active

    try:
        db.flush()

        create_audit_log(
            db,
            user=current_user,
            action=action,
            entity_type="Contract",
            entity_id=contract.id,
            description=description,
            old_values=old_values,
            new_values=contract_snapshot(
                contract,
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
        db.refresh(contract)

    except Exception:
        db.rollback()
        raise

    return contract