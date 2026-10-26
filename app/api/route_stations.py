from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.route_station import RouteStation
from app.models.route import Route
from app.models.station import Station
from app.models.contract import Contract
from app.models.user import User
from app.schemas.route_station import (
    RouteStationCreate,
    RouteStationResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_company_user,
)
from app.core.roles import Roles


router = APIRouter(
    prefix="/route-stations",
    tags=["Route Stations"],
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
            detail="شما مجوز مدیریت ایستگاه‌های مسیر را ندارید",
        )


def check_view_role(
    current_user: User,
) -> None:

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده ایستگاه‌های مسیر را ندارید",
        )


def get_route_or_404(
    db: Session,
    route_id: int,
) -> Route:

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


def get_station_or_404(
    db: Session,
    station_id: int,
) -> Station:

    station = (
        db.query(Station)
        .filter(Station.id == station_id)
        .first()
    )

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه پیدا نشد",
        )

    return station


def check_company_route_access(
    db: Session,
    current_user: User,
    route: Route,
) -> Contract:

    check_company_user(current_user)

    contract = (
        db.query(Contract)
        .filter(
            Contract.transport_company_id
            == current_user.transport_company_id,
            Contract.university_id == route.university_id,
            Contract.is_active.is_(True),
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شرکت شما با دانشگاه این مسیر قرارداد فعال ندارد",
        )

    return contract


def check_company_station_access(
    db: Session,
    current_user: User,
    station: Station,
) -> Contract:

    check_company_user(current_user)

    contract = (
        db.query(Contract)
        .filter(
            Contract.transport_company_id
            == current_user.transport_company_id,
            Contract.university_id == station.university_id,
            Contract.is_active.is_(True),
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شرکت شما با دانشگاه این ایستگاه قرارداد فعال ندارد",
        )

    return contract


def check_route_access(
    db: Session,
    current_user: User,
    route: Route,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_route_access(
            db,
            current_user,
            route,
        )
        return

    check_university_access(
        current_user,
        route.university_id,
    )


def validate_route_and_station(
    db: Session,
    current_user: User,
    route: Route,
    station: Station,
) -> None:

    if not route.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان افزودن ایستگاه به مسیر غیرفعال وجود ندارد",
        )

    if not station.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ایستگاه موردنظر غیرفعال است",
        )

    if route.university_id != station.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر و ایستگاه متعلق به یک دانشگاه نیستند",
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_route_access(
            db,
            current_user,
            route,
        )
    else:
        check_university_access(
            current_user,
            route.university_id,
        )


@router.post(
    "/",
    response_model=RouteStationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route_station(
    data: RouteStationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(current_user)

    route = get_route_or_404(
        db,
        data.route_id,
    )

    station = get_station_or_404(
        db,
        data.station_id,
    )

    validate_route_and_station(
        db,
        current_user,
        route,
        station,
    )

    existing_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == data.route_id,
            RouteStation.station_id == data.station_id,
        )
        .first()
    )

    if existing_station:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ایستگاه قبلاً به این مسیر اضافه شده است",
        )

    existing_order = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == data.route_id,
            RouteStation.stop_order == data.stop_order,
        )
        .first()
    )

    if existing_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ترتیب قبلاً برای یک ایستگاه دیگر استفاده شده است",
        )

    route_station = RouteStation(
        route_id=data.route_id,
        station_id=data.station_id,
        stop_order=data.stop_order,
        estimated_minutes_from_start=data.estimated_minutes_from_start,
        stop_duration_seconds=data.stop_duration_seconds,
    )

    db.add(route_station)
    db.commit()
    db.refresh(route_station)

    return route_station


@router.get(
    "/",
    response_model=list[RouteStationResponse],
)
def get_route_stations(
    route_id: int | None = None,
    station_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(current_user)

    query = db.query(RouteStation)

    # ---------------------------------------------------------
    # Company Admin
    # ---------------------------------------------------------
    if current_user.role == Roles.COMPANY_ADMIN:

        check_company_user(current_user)

        query = (
            query
            .join(
                Route,
                Route.id == RouteStation.route_id,
            )
            .join(
                Contract,
                Contract.university_id == Route.university_id,
            )
            .filter(
                Contract.transport_company_id
                == current_user.transport_company_id,
                Contract.is_active.is_(True),
            )
        )

    # ---------------------------------------------------------
    # سایر کاربران
    # ---------------------------------------------------------
    elif current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = (
            query
            .join(
                Route,
                Route.id == RouteStation.route_id,
            )
            .filter(
                Route.university_id
                == current_user.university_id,
            )
        )

    if route_id is not None:
        query = query.filter(
            RouteStation.route_id == route_id,
        )

    if station_id is not None:
        query = query.filter(
            RouteStation.station_id == station_id,
        )

    return (
        query
        .order_by(
            RouteStation.route_id,
            RouteStation.stop_order,
        )
        .all()
    )


@router.get(
    "/{route_station_id}",
    response_model=RouteStationResponse,
)
def get_route_station(
    route_station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(current_user)

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.id == route_station_id,
        )
        .first()
    )

    if route_station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه مسیر پیدا نشد",
        )

    route = get_route_or_404(
        db,
        route_station.route_id,
    )

    check_route_access(
        db,
        current_user,
        route,
    )

    return route_station


@router.patch(
    "/{route_station_id}",
    response_model=RouteStationResponse,
)
def update_route_station(
    route_station_id: int,
    data: RouteStationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(current_user)

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.id == route_station_id,
        )
        .first()
    )

    if route_station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه مسیر پیدا نشد",
        )

    route = get_route_or_404(
        db,
        route_station.route_id,
    )

    check_route_access(
        db,
        current_user,
        route,
    )

    if data.route_id != route.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر مسیر از این بخش وجود ندارد",
        )

    station = get_station_or_404(
        db,
        data.station_id,
    )

    validate_route_and_station(
        db,
        current_user,
        route,
        station,
    )

    existing_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == route.id,
            RouteStation.station_id == data.station_id,
            RouteStation.id != route_station.id,
        )
        .first()
    )

    if existing_station:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ایستگاه قبلاً به این مسیر اضافه شده است",
        )

    existing_order = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == route.id,
            RouteStation.stop_order == data.stop_order,
            RouteStation.id != route_station.id,
        )
        .first()
    )

    if existing_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این ترتیب قبلاً استفاده شده است",
        )

    route_station.station_id = data.station_id
    route_station.stop_order = data.stop_order
    route_station.estimated_minutes_from_start = (
        data.estimated_minutes_from_start
    )
    route_station.stop_duration_seconds = (
        data.stop_duration_seconds
    )

    db.commit()
    db.refresh(route_station)

    return route_station


@router.delete(
    "/{route_station_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_route_station(
    route_station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(current_user)

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.id == route_station_id,
        )
        .first()
    )

    if route_station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه مسیر پیدا نشد",
        )

    route = get_route_or_404(
        db,
        route_station.route_id,
    )

    check_route_access(
        db,
        current_user,
        route,
    )

    db.delete(route_station)
    db.commit()

    return None