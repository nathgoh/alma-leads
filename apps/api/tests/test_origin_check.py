import pytest
from httpx import AsyncClient

from app.db.models import User
from tests.conftest import PASSWORD

LEAD_ID = "00000000-0000-0000-0000-000000000000"
WRITES = [
    ("PATCH", f"/api/v1/leads/{LEAD_ID}", {"json": {"state": "REACHED_OUT"}}),
    ("POST", "/api/v1/auth/login", {"json": {"email": "attorney@example.com", "password": PASSWORD}}),
    ("POST", "/api/v1/auth/logout", {}),
    ("POST", "/api/v1/leads", {"data": {"firstName": "a"}}),
]


@pytest.mark.parametrize(("method", "url", "kwargs"), WRITES)
@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": None},  # missing Origin → not our browser client
        {"Origin": "https://evil.example"},
        {"Origin": "http://localhost:8025"},  # same-site (Mailpit) is still not same-origin
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
async def test_unsafe_requests_need_our_origin(
    authed: AsyncClient, method: str, url: str, kwargs: dict, headers: dict
) -> None:  # type: ignore[type-arg]
    if headers.get("Origin", "") is None:
        del authed.headers["Origin"]
        headers = {}
    res = await authed.request(method, url, headers=headers, **kwargs)
    assert res.status_code == 403
    assert res.json() == {"detail": "Cross-origin request rejected"}


async def test_same_origin_fetch_passes(authed: AsyncClient) -> None:
    res = await authed.post("/api/v1/auth/logout", headers={"Sec-Fetch-Site": "same-origin"})
    assert res.status_code == 204


async def test_safe_methods_need_no_origin(authed: AsyncClient, attorney: User) -> None:
    del authed.headers["Origin"]
    assert (await authed.get("/api/v1/auth/me")).status_code == 200


async def test_no_cors_headers_are_ever_sent(authed: AsyncClient) -> None:
    res = await authed.get("/api/v1/auth/me", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers
    preflight = await authed.options(
        "/api/v1/leads/x",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "PATCH"},
    )
    assert "access-control-allow-origin" not in preflight.headers
