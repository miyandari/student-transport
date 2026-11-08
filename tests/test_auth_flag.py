from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(u, p):
    return client.post("/auth/login", data={"username": u, "password": p})


def test_login_returns_flag_and_change_clears_it(db):
    from app.models.user import User

    u = db.query(User).filter_by(username="demo_admin").one()
    u.must_change_password = True
    db.commit()

    r = _login("demo_admin", "Admin@Demo123")
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r2 = client.patch("/users/me/password", headers=h,
                      json={"current_password": "Admin@Demo123", "new_password": "Admin@Demo456"})
    assert r2.status_code == 200, r2.text
    r3 = _login("demo_admin", "Admin@Demo456")
    assert r3.json()["must_change_password"] is False
    # برگرداندن رمز برای تست‌های دیگر
    h = {"Authorization": f"Bearer {r3.json()['access_token']}"}
    client.patch("/users/me/password", headers=h,
                 json={"current_password": "Admin@Demo456", "new_password": "Admin@Demo123"})


def test_students_pagination_optional():
    r = _login("demo_admin", "Admin@Demo123")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    all_ = client.get("/students/", headers=h)
    assert all_.status_code == 200, all_.text
    page = client.get("/students/?limit=5&skip=2", headers=h)
    assert page.status_code == 200
    assert [x["id"] for x in page.json()] == [x["id"] for x in all_.json()][2:7]
    assert client.get("/trips/?limit=3", headers=h).status_code == 200
    assert client.get("/reservations/?limit=3", headers=h).status_code == 200
