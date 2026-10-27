from fastapi import FastAPI

from app.api.router import router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.universities import router as universities_router
from app.api.students import router as students_router
from app.api.drivers import router as drivers_router
from app.api.vehicles import router as vehicles_router
from app.api.contracts import router as contracts_router
from app.api.stations import router as stations_router
from app.api.routes import router as routes_router
from app.api.route_stations import router as route_stations_router
from app.api.services import router as services_router
from app.api.schedules import router as schedules_router
from app.api.trips import router as trips_router
from app.api.trip_passengers import router as trip_passengers_router
from app.api.reservations import router as reservations_router
from app.api.vehicle_locations import router as vehicle_locations_router
from app.api.vehicle_location_ws import router as vehicle_location_ws_router
from app.api.trip_incidents import router as trip_incidents_router
from app.api.feedbacks import router as feedbacks_router


app = FastAPI(
    title="سامانه مدیریت سرویس ایاب و ذهاب دانشجویی",
    description="Backend سامانه مدیریت سرویس ایاب و ذهاب دانشجویان",
    version="1.0.0",
)


# =========================================================
# Core Router
# =========================================================

app.include_router(router)


# =========================================================
# Authentication & Users
# =========================================================

app.include_router(auth_router)
app.include_router(users_router)


# =========================================================
# University & Student
# =========================================================

app.include_router(universities_router)
app.include_router(students_router)


# =========================================================
# Transport Resources
# =========================================================

app.include_router(drivers_router)
app.include_router(vehicles_router)
app.include_router(contracts_router)


# =========================================================
# Stations & Routes
# =========================================================

app.include_router(stations_router)
app.include_router(routes_router)
app.include_router(route_stations_router)


# =========================================================
# Services, Schedules & Trips
# =========================================================

app.include_router(services_router)
app.include_router(schedules_router)
app.include_router(trips_router)
app.include_router(trip_passengers_router)
app.include_router(reservations_router)


# =========================================================
# Vehicle Tracking
# =========================================================

app.include_router(vehicle_locations_router)
app.include_router(vehicle_location_ws_router)


# =========================================================
# Trip Incidents & Feedback
# =========================================================

app.include_router(trip_incidents_router)
app.include_router(feedbacks_router)