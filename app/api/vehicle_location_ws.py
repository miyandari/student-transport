from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.models.trip import Trip
from app.models.vehicle import Vehicle
from app.models.vehicle_location import VehicleLocation

from app.core.security import SECRET_KEY, ALGORITHM
from app.core.roles import ALL_ROLES, Roles
from app.core.dependencies import (
    check_university_access,
    check_trip_company_access,
    check_vehicle_company_access,
)

from app.realtime.connection_manager import connection_manager


router = APIRouter(
    tags=["Vehicle Location WebSocket"],
)


ALLOWED_TRIP_STATUSES = {
    "boarding",
    "in_progress",
}


async def websocket_error(
    websocket: WebSocket,
    message: str,
    code: int = 1008,
):
    try:
        await websocket.send_json({
            "type": "error",
            "message": message,
        })
    except Exception:
        pass

    try:
        await websocket.close(code=code)
    except Exception:
        pass


@router.websocket("/ws/trips/{trip_id}/location")
async def vehicle_location_websocket(
    websocket: WebSocket,
    trip_id: int,
):
    print(">>> WebSocket request received")
    print(">>> Trip ID:", trip_id)

    await websocket.accept()

    print(">>> WebSocket accepted")

    token = websocket.query_params.get("token")

    if not token:
        await websocket_error(
            websocket,
            "Token ارسال نشده است",
        )
        return

    db: Session = SessionLocal()
    connected = False

    try:

        # -------------------------------------------------
        # 1. بررسی JWT
        # -------------------------------------------------

        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
            )

            user_id = payload.get("sub")

            if user_id is None:
                raise JWTError("sub missing")

            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                raise JWTError("invalid user id")

        except JWTError:
            await websocket_error(
                websocket,
                "JWT نامعتبر است",
            )
            return

        # -------------------------------------------------
        # 2. پیدا کردن کاربر
        # -------------------------------------------------

        current_user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if current_user is None:
            await websocket_error(
                websocket,
                "کاربر یافت نشد",
            )
            return

        # -------------------------------------------------
        # 3. بررسی فعال بودن حساب
        # -------------------------------------------------

        if not current_user.is_active:
            await websocket_error(
                websocket,
                "حساب کاربری غیرفعال است",
            )
            return

        # -------------------------------------------------
        # 4. بررسی نقش
        # -------------------------------------------------

        if current_user.role not in ALL_ROLES:
            await websocket_error(
                websocket,
                "نقش کاربری نامعتبر است",
            )
            return

        # -------------------------------------------------
        # 5. پیدا کردن سفر
        # -------------------------------------------------

        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id)
            .first()
        )

        if trip is None:
            await websocket_error(
                websocket,
                "سفر موردنظر یافت نشد",
            )
            return

        # -------------------------------------------------
        # 6. بررسی فعال بودن سفر
        # -------------------------------------------------

        if not trip.is_active:
            await websocket_error(
                websocket,
                "این سفر غیرفعال است",
            )
            return

        # -------------------------------------------------
        # 7. بررسی وضعیت سفر
        # -------------------------------------------------

        if trip.status not in ALLOWED_TRIP_STATUSES:
            await websocket_error(
                websocket,
                "در وضعیت فعلی سفر امکان اتصال وجود ندارد",
            )

            try:
                await websocket.send_json({
                    "type": "trip_status",
                    "trip_status": trip.status,
                })
            except Exception:
                pass

            return

        # -------------------------------------------------
        # 8. بررسی دسترسی بر اساس نقش
        # -------------------------------------------------

        if current_user.role == Roles.COMPANY_ADMIN:

            check_trip_company_access(
                db,
                current_user,
                trip,
            )

        else:

            check_university_access(
                current_user=current_user,
                university_id=trip.university_id,
            )

        # -------------------------------------------------
        # 9. بررسی دسترسی راننده
        # -------------------------------------------------

        if current_user.role == Roles.DRIVER:

            if current_user.driver_id is None:
                await websocket_error(
                    websocket,
                    "حساب راننده به راننده‌ای متصل نیست",
                )
                return

            if trip.driver_id != current_user.driver_id:
                await websocket_error(
                    websocket,
                    "شما راننده این سفر نیستید",
                )
                return

        # -------------------------------------------------
        # 10. بررسی خودرو
        # -------------------------------------------------

        if trip.vehicle_id is None:
            await websocket_error(
                websocket,
                "برای این سفر خودرویی تعیین نشده است",
            )
            return

        vehicle = (
            db.query(Vehicle)
            .filter(Vehicle.id == trip.vehicle_id)
            .first()
        )

        if vehicle is None:
            await websocket_error(
                websocket,
                "خودروی سفر یافت نشد",
            )
            return

        # -------------------------------------------------
        # 11. کنترل دسترسی شرکت به خودرو
        # -------------------------------------------------

        if current_user.role == Roles.COMPANY_ADMIN:

            check_vehicle_company_access(
                db,
                current_user,
                vehicle,
            )

        # -------------------------------------------------
        # 12. بررسی هماهنگی دانشگاه سفر و خودرو
        # -------------------------------------------------

        if vehicle.university_id != trip.university_id:
            await websocket_error(
                websocket,
                "خودرو و سفر متعلق به یک دانشگاه نیستند",
            )
            return

        # -------------------------------------------------
        # 13. ارسال پیام احراز هویت موفق
        # -------------------------------------------------

        await websocket.send_json({
            "type": "auth",
            "message": "احراز هویت و دسترسی با موفقیت انجام شد",
            "user_id": current_user.id,
            "role": current_user.role,
            "trip_id": trip.id,
            "vehicle_id": vehicle.id,
        })

        # -------------------------------------------------
        # 14. ثبت اتصال در ConnectionManager
        # -------------------------------------------------

        await connection_manager.connect(
            trip_id,
            websocket,
        )

        connected = True

        # -------------------------------------------------
        # 15. ارسال آخرین موقعیت ثبت‌شده خودرو
        # -------------------------------------------------

        latest_location = (
            db.query(VehicleLocation)
            .filter(
                VehicleLocation.trip_id == trip_id,
                VehicleLocation.vehicle_id == vehicle.id,
            )
            .order_by(
                VehicleLocation.recorded_at.desc()
            )
            .first()
        )

        if latest_location is not None:

            await websocket.send_json({
                "type": "last_vehicle_location",
                "trip_id": latest_location.trip_id,
                "vehicle_id": latest_location.vehicle_id,
                "latitude": latest_location.latitude,
                "longitude": latest_location.longitude,
                "speed": latest_location.speed,
                "heading": latest_location.heading,
                "recorded_at": (
                    latest_location.recorded_at.isoformat()
                ),
            })

        # -------------------------------------------------
        # 16. اعلام آماده بودن WebSocket
        # -------------------------------------------------

        await websocket.send_json({
            "type": "ready",
            "message": "WebSocket آماده دریافت موقعیت است",
            "trip_id": trip.id,
            "trip_status": trip.status,
            "vehicle_id": vehicle.id,
        })

        print(
            f">>> WebSocket connected "
            f"(user={current_user.id}, "
            f"role={current_user.role}, "
            f"trip={trip_id}, "
            f"vehicle={vehicle.id})"
        )

        # -------------------------------------------------
        # 17. نگه داشتن اتصال
        # -------------------------------------------------

        try:

            while True:
                await websocket.receive_text()

        except WebSocketDisconnect:

            print(
                f">>> WebSocket disconnected "
                f"(user={current_user.id}, "
                f"trip={trip_id})"
            )

    except WebSocketDisconnect:

        print(
            f">>> WebSocket disconnected "
            f"(user={current_user.id if 'current_user' in locals() else 'unknown'}, "
            f"trip={trip_id})"
        )

    except Exception as exc:

        print(
            f">>> WebSocket error: {exc}"
        )

        if connected:
            connection_manager.disconnect(
                trip_id,
                websocket,
            )
            connected = False

        try:
            await websocket.close(code=1011)
        except Exception:
            pass

    finally:

        if connected:
            connection_manager.disconnect(
                trip_id,
                websocket,
            )

        db.close()