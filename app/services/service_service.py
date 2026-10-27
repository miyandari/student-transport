from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.route import Route
from app.models.contract import Contract
from app.models.university import University


ALLOWED_GENDER_RESTRICTIONS = {
    "mixed",
    "male",
    "female",
}


def get_service(
    db: Session,
    service_id: int,
) -> Service:
    if service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
        )

    service = (
        db.query(Service)
        .filter(Service.id == service_id)
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس پیدا نشد",
        )

    return service


def get_university(
    db: Session,
    university_id: int,
) -> University:
    if university_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه دانشگاه نامعتبر است",
        )

    university = (
        db.query(University)
        .filter(University.id == university_id)
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


def get_route(
    db: Session,
    route_id: int,
) -> Route:
    if route_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه مسیر نامعتبر است",
        )

    route = (
        db.query(Route)
        .filter(Route.id == route_id)
        .first()
    )

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="مسیر موردنظر پیدا نشد",
        )

    return route


def get_contract(
    db: Session,
    contract_id: int,
) -> Contract:
    if contract_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه قرارداد نامعتبر است",
        )

    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="قرارداد موردنظر پیدا نشد",
        )

    return contract


def normalize_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def validate_gender_restriction(
    value: str | None,
) -> str:
    value = normalize_text(value)

    if value is None:
        value = "mixed"

    value = value.lower()

    if value not in ALLOWED_GENDER_RESTRICTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="محدودیت جنسیتی سرویس نامعتبر است",
        )

    return value


def validate_service_data(
    db: Session,
    *,
    university_id: int,
    route_id: int,
    contract_id: int | None,
    name: str,
    code: str,
    service_type: str,
    gender_restriction: str = "mixed",
    is_active: bool = False,
) -> tuple[str, str, str, str]:

    name = normalize_text(name)
    code = normalize_text(code)
    service_type = normalize_text(service_type)

    gender_restriction = validate_gender_restriction(
        gender_restriction
    )

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام سرویس نمی‌تواند خالی باشد",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد سرویس نمی‌تواند خالی باشد",
        )

    if not service_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع سرویس نمی‌تواند خالی باشد",
        )

    get_university(
        db,
        university_id,
    )

    route = get_route(
        db,
        route_id,
    )

    if route.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر متعلق به دانشگاه انتخاب‌شده نیست",
        )

    if not route.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر انتخاب‌شده غیرفعال است",
        )

    if contract_id is not None:
        contract = get_contract(
            db,
            contract_id,
        )

        if contract.university_id != university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="قرارداد متعلق به این دانشگاه نیست",
            )

        if not contract.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="قرارداد انتخاب‌شده غیرفعال است",
            )

    return (
        name,
        code,
        service_type,
        gender_restriction,
    )


def validate_unique_service_code(
    db: Session,
    *,
    university_id: int,
    code: str,
    service_id: int | None = None,
) -> None:

    query = (
        db.query(Service)
        .filter(
            Service.university_id == university_id,
            Service.code == code,
        )
    )

    if service_id is not None:
        if service_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه سرویس نامعتبر است",
            )

        query = query.filter(
            Service.id != service_id
        )

    existing = query.first()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد این سرویس قبلاً در این دانشگاه ثبت شده است",
        )


def create_service(
    db: Session,
    *,
    university_id: int,
    route_id: int,
    contract_id: int | None,
    name: str,
    code: str,
    service_type: str,
    gender_restriction: str = "mixed",
    is_active: bool = False,
) -> Service:

    (
        name,
        code,
        service_type,
        gender_restriction,
    ) = validate_service_data(
        db,
        university_id=university_id,
        route_id=route_id,
        contract_id=contract_id,
        name=name,
        code=code,
        service_type=service_type,
        gender_restriction=gender_restriction,
        is_active=is_active,
    )

    validate_unique_service_code(
        db,
        university_id=university_id,
        code=code,
    )

    service = Service(
        university_id=university_id,
        route_id=route_id,
        contract_id=contract_id,
        name=name,
        code=code,
        service_type=service_type,
        gender_restriction=gender_restriction,
        is_active=is_active,
    )

    try:
        db.add(service)
        db.commit()
        db.refresh(service)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="امکان ثبت سرویس وجود ندارد؛ احتمالاً کد سرویس تکراری است",
        )

    except Exception:
        db.rollback()
        raise

    return service


def get_services(
    db: Session,
    *,
    university_id: int | None = None,
    route_id: int | None = None,
    contract_id: int | None = None,
    service_type: str | None = None,
    gender_restriction: str | None = None,
    is_active: bool | None = None,
) -> list[Service]:

    query = db.query(Service)

    if university_id is not None:
        if university_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه دانشگاه نامعتبر است",
            )

        query = query.filter(
            Service.university_id == university_id
        )

    if route_id is not None:
        if route_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه مسیر نامعتبر است",
            )

        query = query.filter(
            Service.route_id == route_id
        )

    if contract_id is not None:
        if contract_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه قرارداد نامعتبر است",
            )

        query = query.filter(
            Service.contract_id == contract_id
        )

    service_type = normalize_text(service_type)

    if service_type:
        query = query.filter(
            Service.service_type == service_type
        )

    if gender_restriction is not None:
        gender_restriction = validate_gender_restriction(
            gender_restriction
        )

        query = query.filter(
            Service.gender_restriction == gender_restriction
        )

    if is_active is not None:
        query = query.filter(
            Service.is_active == is_active
        )

    return (
        query
        .order_by(Service.id.desc())
        .all()
    )


def update_service(
    db: Session,
    *,
    service_id: int,
    university_id: int,
    route_id: int,
    contract_id: int | None,
    name: str,
    code: str,
    service_type: str,
    gender_restriction: str = "mixed",
    is_active: bool = False,
) -> Service:

    service = get_service(
        db,
        service_id,
    )

    if service.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه سرویس وجود ندارد",
        )

    (
        name,
        code,
        service_type,
        gender_restriction,
    ) = validate_service_data(
        db,
        university_id=university_id,
        route_id=route_id,
        contract_id=contract_id,
        name=name,
        code=code,
        service_type=service_type,
        gender_restriction=gender_restriction,
        is_active=is_active,
    )

    validate_unique_service_code(
        db,
        university_id=university_id,
        code=code,
        service_id=service.id,
    )

    service.route_id = route_id
    service.contract_id = contract_id
    service.name = name
    service.code = code
    service.service_type = service_type
    service.gender_restriction = gender_restriction
    service.is_active = is_active

    try:
        db.commit()
        db.refresh(service)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="امکان ویرایش سرویس وجود ندارد؛ احتمالاً کد سرویس تکراری است",
        )

    except Exception:
        db.rollback()
        raise

    return service


def update_service_status(
    db: Session,
    *,
    service_id: int,
    is_active: bool,
) -> Service:

    service = get_service(
        db,
        service_id,
    )

    if is_active:
        validate_service_data(
            db,
            university_id=service.university_id,
            route_id=service.route_id,
            contract_id=service.contract_id,
            name=service.name,
            code=service.code,
            service_type=service.service_type,
            gender_restriction=service.gender_restriction,
            is_active=True,
        )

    service.is_active = is_active

    try:
        db.commit()
        db.refresh(service)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="امکان تغییر وضعیت سرویس وجود ندارد",
        )

    except Exception:
        db.rollback()
        raise

    return service