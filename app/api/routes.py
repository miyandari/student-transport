from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.route import Route
from app.models.university import University
from app.models.user import User

from app.schemas.route import (
    RouteCreate,
    RouteResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
)

from app.core.roles import Roles


router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)


# =========================================================
# Helpers
# =========================================================

def normalize_text(
    value: str | None,
):
    if value is None:
        return None

    return value.strip()


def check_management_role(
    current_user: User,
):
    allowed_roles = {
        Roles.SUPER_ADMIN,
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
    }

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت مسیرها را ندارید",
        )


def check_view_role(
    current_user: User,
):
    allowed_roles = {
        Roles.SUPER_ADMIN,
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
        Roles.DRIVER,
        Roles.STUDENT,
    }

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده مسیرها را ندارید",
        )


def validate_direction(
    direction: str,
):
    if direction not in {
        "outbound",
        "inbound",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="جهت مسیر باید outbound یا inbound باشد",
        )


def get_route_or_404(
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
            detail="مسیر پیدا نشد",
        )

    return route


def validate_university(
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


def validate_route_data(
    db: Session,
    route_data: RouteCreate,
    current_route_id: int | None = None,
):
    name = normalize_text(
        route_data.name
    )

    code = normalize_text(
        route_data.code
    )

    description = normalize_text(
        route_data.description
    )

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام مسیر نمی‌تواند خالی باشد",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد مسیر نمی‌تواند خالی باشد",
        )

    validate_direction(
        route_data.direction
    )

    query = (
        db.query(Route)
        .filter(
            Route.university_id == route_data.university_id,
            Route.code == code,
        )
    )

    if current_route_id is not None:
        query = query.filter(
            Route.id != current_route_id
        )

    existing_route = query.first()

    if existing_route is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد این مسیر قبلاً در این دانشگاه ثبت شده است",
        )

    return (
        name,
        code,
        description,
    )


# =========================================================
# Create Route
# =========================================================

@router.post(
    "/",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route(
    route_data: RouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(
        current_user
    )

    validate_university(
        db=db,
        university_id=route_data.university_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=route_data.university_id,
    )

    name, code, description = validate_route_data(
        db=db,
        route_data=route_data,
    )

    route = Route(
        university_id=route_data.university_id,
        name=name,
        code=code,
        direction=route_data.direction,
        description=description,
        is_active=route_data.is_active,
    )

    db.add(route)

    try:
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise

    return route


# =========================================================
# Get Routes
# =========================================================

@router.get(
    "/",
    response_model=list[RouteResponse],
)
def get_routes(
    university_id: int | None = None,
    direction: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user
    )

    query = db.query(Route)

    # -----------------------------------------------------
    # Super Admin
    # -----------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:

        if university_id is not None:
            query = query.filter(
                Route.university_id == university_id
            )

    # -----------------------------------------------------
    # University Users / Driver / Student
    # -----------------------------------------------------

    else:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Route.university_id
            == current_user.university_id
        )

        if university_id is not None:
            if university_id != current_user.university_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="شما به مسیرهای این دانشگاه دسترسی ندارید",
                )

    # -----------------------------------------------------
    # Direction
    # -----------------------------------------------------

    if direction is not None:

        validate_direction(
            direction
        )

        query = query.filter(
            Route.direction == direction
        )

    # -----------------------------------------------------
    # Active Filter
    # -----------------------------------------------------

    if is_active is not None:

        query = query.filter(
            Route.is_active == is_active
        )

    return (
        query
        .order_by(
            Route.id.desc()
        )
        .all()
    )


# =========================================================
# Get Route By ID
# =========================================================

@router.get(
    "/{route_id}",
    response_model=RouteResponse,
)
def get_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user
    )

    route = get_route_or_404(
        db=db,
        route_id=route_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=route.university_id,
    )

    return route


# =========================================================
# Update Route
# =========================================================

@router.patch(
    "/{route_id}",
    response_model=RouteResponse,
)
def update_route(
    route_id: int,
    route_data: RouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(
        current_user
    )

    route = get_route_or_404(
        db=db,
        route_id=route_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=route.university_id,
    )

    if (
        route_data.university_id
        != route.university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه مسیر از این بخش وجود ندارد",
        )

    name, code, description = validate_route_data(
        db=db,
        route_data=route_data,
        current_route_id=route.id,
    )

    route.name = name
    route.code = code
    route.direction = route_data.direction
    route.description = description
    route.is_active = route_data.is_active

    try:
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise

    return route


# =========================================================
# Update Route Status
# =========================================================

@router.patch(
    "/{route_id}/status",
    response_model=RouteResponse,
)
def update_route_status(
    route_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(
        current_user
    )

    route = get_route_or_404(
        db=db,
        route_id=route_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=route.university_id,
    )

    route.is_active = is_active

    try:
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise

    return route