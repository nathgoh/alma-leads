from httpx import AsyncClient

from app.db.models import User
from tests.conftest import PASSWORD


async def test_login_sets_hardened_session_cookie(client: AsyncClient, attorney: User) -> None:
    res = await client.post(
        "/api/v1/auth/login", json={"email": "Attorney@Example.com", "password": PASSWORD}
    )
    assert res.status_code == 200
    assert res.json()["email"] == "attorney@example.com"
    cookie = res.headers["set-cookie"].lower()
    assert cookie.startswith("session=")
    for attr in ("httponly", "samesite=lax", "path=/", "max-age=28800"):
        assert attr in cookie
    assert "domain=" not in cookie


async def test_full_auth_flow(client: AsyncClient, attorney: User) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    await client.post("/api/v1/auth/login", json={"email": attorney.email, "password": PASSWORD})

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["id"] == attorney.id
    assert (await client.get("/api/v1/leads")).status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert 'session=""' in logout.headers["set-cookie"] or "max-age=0" in logout.headers["set-cookie"].lower()
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/leads")).status_code == 401


async def test_wrong_password_and_unknown_user_look_the_same(client: AsyncClient, attorney: User) -> None:
    wrong = await client.post("/api/v1/auth/login", json={"email": attorney.email, "password": "nope"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "who@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


async def test_tampered_token_is_rejected(client: AsyncClient, attorney: User) -> None:
    client.cookies.set("session", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0.")
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_login_requires_json(client: AsyncClient, attorney: User) -> None:
    res = await client.post("/api/v1/auth/login", data={"email": attorney.email, "password": PASSWORD})
    assert res.status_code == 415


async def test_login_is_rate_limited(client: AsyncClient, attorney: User) -> None:
    codes = [
        (await client.post("/api/v1/auth/login", json={"email": attorney.email, "password": "x"})).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
