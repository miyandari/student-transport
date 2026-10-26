from fastapi import FastAPI

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