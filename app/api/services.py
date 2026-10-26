from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.service import Service
from app.models.contract import Contract
from app.models.route import Route

from app.schemas.service import (
    ServiceCreate,
    ServiceResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_company_user,
    check_company_contract_access,
)

from app.core.roles import Roles

from app.services.service_service import (
    get_service,
    create_service,
    get_services,
    update_service,
    update_service_status,
)


router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
}

VIEW_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
    Roles.DRIVER,
    Roles.STUDENT,
}


def check_management_role(
    current_user: User,
) -> None:
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت سرویس‌ها را ندارید",
        )


def check_view_role(
    current_user: User,
) -> None:
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده سرویس‌ها را ندارید",
        )


def get_active_route(
    db: Session,
    route_id: int,
    university_id: int,
) -> Route:
    if route_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه مسیر نامعتبر است",
        )

    route = (
        db.query(Route)
        .filter(
            Route.id == route_id,
        )
        .first()
    )

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="مسیر موردنظر پیدا نشد",
        )

    if route.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="مسیر متعلق به دانشگاه سرویس نیست",
        )

    if not route.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر موردنظر غیرفعال است",
        )

    return route


def get_active_contract(
    db: Session,
    contract_id: int,
    university_id: int,
) -> Contract:
    if contract_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه قرارداد نامعتبر است",
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
            detail="قرارداد موردنظر پیدا نشد",
        )

    if contract.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد متعلق به دانشگاه سرویس نیست",
        )

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد موردنظر غیرفعال است",
        )

    return contract


def check_route_access(
    db: Session,
    current_user: User,
    route_id: int,
    university_id: int,
) -> Route:
    route = get_active_route(
        db=db,
        route_id=route_id,
        university_id=university_id,
    )

    if current_user.role != Roles.COMPANY_ADMIN:
        check_university_access(
            current_user=current_user,
            university_id=university_id,
        )

    return route


def check_company_service_access(
    db: Session,
    current_user: User,
    service: Service,
) -> Contract:
    check_company_user(current_user)

    if service.contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس تحت قرارداد شرکت حمل‌ونقل قرار ندارد",
        )

    contract = check_company_contract_access(
        db=db,
        current_user=current_user,
        contract_id=service.contract_id,
    )

    if service.university_id != contract.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه سرویس با دانشگاه قرارداد مطابقت ندارد",
        )

    return contract


def check_company_service_data(
    db: Session,
    current_user: User,
    university_id: int,
    route_id: int,
    contract_id: int | None,
) -> Contract:
    check_company_user(current_user)

    if contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای سرویس شرکت، قرارداد باید مشخص شود",
        )

    contract = check_company_contract_access(
        db=db,
        current_user=current_user,
        contract_id=contract_id,
    )

    if contract.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه قرارداد با دانشگاه سرویس مطابقت ندارد",
        )

    check_route_access(
        db=db,
        current_user=current_user,
        route_id=route_id,
        university_id=university_id,
    )

    return contract


@router.post(
    "/",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_endpoint(
    data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_service_data(
            db=db,
            current_user=current_user,
            university_id=data.university_id,
            route_id=data.route_id,
            contract_id=data.contract_id,
        )

    else:
        check_university_access(
            current_user=current_user,
            university_id=data.university_id,
        )

        check_route_access(
            db=db,
            current_user=current_user,
            route_id=data.route_id,
            university_id=data.university_id,
        )

        if data.contract_id is not None:
            get_active_contract(
                db=db,
                contract_id=data.contract_id,
                university_id=data.university_id,
            )

    return create_service(
        db,
        university_id=data.university_id,
        route_id=data.route_id,
        contract_id=data.contract_id,
        name=data.name,
        code=data.code,
        service_type=data.service_type,
        is_active=data.is_active,
    )


@router.get(
    "/",
    response_model=list[ServiceResponse],
)
def get_services_endpoint(
    university_id: int | None = None,
    route_id: int | None = None,
    contract_id: int | None = None,
    service_type: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_view_role(current_user)

    if current_user.role == Roles.SUPER_ADMIN:
        pass

    elif current_user.role == Roles.COMPANY_ADMIN:
        check_company_user(current_user)

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شرکت به شرکت حمل‌ونقلی متصل نیست",
            )

        query = (
            db.query(Service)
            .join(
                Contract,
                Contract.id == Service.contract_id,
            )
            .filter(
                Service.contract_id.isnot(None),
                Contract.transport_company_id
                == current_user.transport_company_id,
                Contract.is_active.is_(True),
            )
        )

        if university_id is not None:
            query = query.filter(
                Service.university_id == university_id,
                Contract.university_id == university_id,
            )

        if route_id is not None:
            query = query.filter(
                Service.route_id == route_id,
            )

        if contract_id is not None:
            query = query.filter(
                Service.contract_id == contract_id,
            )

        if service_type is not None:
            query = query.filter(
                Service.service_type == service_type,
            )

        if is_active is not None:
            query = query.filter(
                Service.is_active == is_active,
            )

        return (
            query
            .order_by(Service.id.asc())
            .all()
        )

    else:
        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        university_id = current_user.university_id

    return get_services(
        db,
        university_id=university_id,
        route_id=route_id,
        contract_id=contract_id,
        service_type=service_type,
        is_active=is_active,
    )


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
)
def get_service_endpoint(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_view_role(current_user)

    if service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
        )

    service = get_service(
        db,
        service_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_service_access(
            db=db,
            current_user=current_user,
            service=service,
        )

    else:
        check_university_access(
            current_user=current_user,
            university_id=service.university_id,
        )

    return service


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
)
def update_service_endpoint(
    service_id: int,
    data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    if service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
        )

    service = get_service(
        db,
        service_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        contract = check_company_service_access(
            db=db,
            current_user=current_user,
            service=service,
        )

        if data.university_id != service.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="امکان تغییر دانشگاه سرویس وجود ندارد",
            )

        if data.contract_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای سرویس شرکت، قرارداد باید مشخص شود",
            )

        new_contract = check_company_contract_access(
            db=db,
            current_user=current_user,
            contract_id=data.contract_id,
        )

        if new_contract.university_id != service.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="قرارداد جدید متعلق به دانشگاه سرویس نیست",
            )

        check_route_access(
            db=db,
            current_user=current_user,
            route_id=data.route_id,
            university_id=service.university_id,
        )

    else:
        check_university_access(
            current_user=current_user,
            university_id=service.university_id,
        )

        if data.university_id != service.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="امکان تغییر دانشگاه سرویس وجود ندارد",
            )

        check_route_access(
            db=db,
            current_user=current_user,
            route_id=data.route_id,
            university_id=service.university_id,
        )

        if data.contract_id is not None:
            get_active_contract(
                db=db,
                contract_id=data.contract_id,
                university_id=service.university_id,
            )

    return update_service(
        db,
        service_id=service_id,
        university_id=data.university_id,
        route_id=data.route_id,
        contract_id=data.contract_id,
        name=data.name,
        code=data.code,
        service_type=data.service_type,
        is_active=data.is_active,
    )


@router.patch(
    "/{service_id}/status",
    response_model=ServiceResponse,
)
def update_service_status_endpoint(
    service_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    if service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
        )

    service = get_service(
        db,
        service_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_service_access(
            db=db,
            current_user=current_user,
            service=service,
        )

    else:
        check_university_access(
            current_user=current_user,
            university_id=service.university_id,
        )

    return update_service_status(
        db,
        service_id=service_id,
        is_active=is_active,
    )
