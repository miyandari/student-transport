from fastapi import FastAPI

from app.api.router import router
from app.api.notifications import router as notifications_router


app = FastAPI(
    title="سامانه مدیریت سرویس ایاب و ذهاب دانشجویی",
    description="Backend سامانه مدیریت سرویس ایاب و ذهاب دانشجویان",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "سامانه مدیریت سرویس ایاب و ذهاب دانشجویی فعال است"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


app.include_router(router)
app.include_router(notifications_router)