import asyncio

import pytest
from httpx import AsyncClient

from app.db.models import User
from tests.conftest import InMemoryStorage, lead_form, resume_file

MISSING = "00000000-0000-0000-0000-000000000000"


async def _submit(client: AsyncClient, **fields: str) -> str:
    res = await client.post("/api/v1/leads", data=lead_form(**fields), files=resume_file())
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/leads"),
        ("GET", f"/api/v1/leads/{MISSING}"),
        ("GET", f"/api/v1/leads/{MISSING}/resume"),
        ("PATCH", f"/api/v1/leads/{MISSING}"),
    ],
)
async def test_internal_routes_require_auth(client: AsyncClient, method: str, path: str) -> None:
    res = await client.request(method, path, json={"state": "REACHED_OUT"} if method == "PATCH" else None)
    assert res.status_code == 401


async def test_list_filters_paginates_and_sorts_newest_first(authed: AsyncClient) -> None:
    ids = [await _submit(authed, firstName=f"Lead{i}") for i in range(3)]
    await authed.patch(f"/api/v1/leads/{ids[0]}", json={"state": "REACHED_OUT"})

    page = (await authed.get("/api/v1/leads", params={"pageSize": 2})).json()
    assert page["total"] == 3 and page["page"] == 1 and page["pageSize"] == 2
    assert [item["id"] for item in page["items"]] == [ids[2], ids[1]]

    page2 = (await authed.get("/api/v1/leads", params={"pageSize": 2, "page": 2})).json()
    assert [item["id"] for item in page2["items"]] == [ids[0]]

    pending = (await authed.get("/api/v1/leads", params={"state": "PENDING"})).json()
    assert {item["id"] for item in pending["items"]} == {ids[1], ids[2]}
    reached = (await authed.get("/api/v1/leads", params={"state": "REACHED_OUT"})).json()
    assert [item["id"] for item in reached["items"]] == [ids[0]]

    oldest = (await authed.get("/api/v1/leads", params={"sort": "oldest"})).json()
    assert [item["id"] for item in oldest["items"]] == ids


async def test_list_rejects_bad_params(authed: AsyncClient) -> None:
    assert (await authed.get("/api/v1/leads", params={"pageSize": 1000})).status_code == 422
    assert (await authed.get("/api/v1/leads", params={"state": "HIRED"})).status_code == 422


async def test_detail_includes_everything_submitted_and_email_status(authed: AsyncClient) -> None:
    lead_id = await _submit(authed)
    detail = (await authed.get(f"/api/v1/leads/{lead_id}")).json()
    assert detail["firstName"] == "Ada" and detail["lastName"] == "Lovelace"
    assert detail["email"] == "ada@example.com"
    assert detail["state"] == "PENDING"
    assert detail["resumeName"] == "cv.pdf" and detail["resumeMime"] == "application/pdf"
    assert detail["reachedOutBy"] is None and detail["reachedOutAt"] is None
    assert {(e["kind"], e["status"]) for e in detail["emails"]} == {
        ("PROSPECT_CONFIRMATION", "SENT"),
        ("ATTORNEY_NOTIFICATION", "SENT"),
    }
    assert "resumeKey" not in detail  # storage keys stay server-side


async def test_detail_404(authed: AsyncClient) -> None:
    assert (await authed.get(f"/api/v1/leads/{MISSING}")).status_code == 404


async def test_mark_reached_out_stamps_who_and_when(authed: AsyncClient, attorney: User) -> None:
    lead_id = await _submit(authed)
    res = await authed.patch(f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"})
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "REACHED_OUT"
    assert body["reachedOutAt"] is not None
    assert body["reachedOutBy"] == {"id": attorney.id, "name": "Attorney", "email": attorney.email}


async def test_second_transition_is_409_not_a_silent_noop(authed: AsyncClient) -> None:
    lead_id = await _submit(authed)
    assert (await authed.patch(f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"})).status_code == 200
    again = await authed.patch(f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"})
    assert again.status_code == 409


async def test_concurrent_transitions_have_exactly_one_winner(authed: AsyncClient) -> None:
    lead_id = await _submit(authed)
    results = await asyncio.gather(
        *(authed.patch(f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}) for _ in range(5))
    )
    assert sorted(r.status_code for r in results) == [200, 409, 409, 409, 409]


async def test_cannot_move_back_to_pending(authed: AsyncClient) -> None:
    lead_id = await _submit(authed)
    res = await authed.patch(f"/api/v1/leads/{lead_id}", json={"state": "PENDING"})
    assert res.status_code == 422  # not even a valid target in the request schema


async def test_patch_unknown_lead_is_404(authed: AsyncClient) -> None:
    assert (await authed.patch(f"/api/v1/leads/{MISSING}", json={"state": "REACHED_OUT"})).status_code == 404


async def test_patch_requires_json(authed: AsyncClient) -> None:
    lead_id = await _submit(authed)
    res = await authed.patch(f"/api/v1/leads/{lead_id}", data={"state": "REACHED_OUT"})
    assert res.status_code == 415


async def test_resume_endpoint_returns_short_lived_url(authed: AsyncClient, storage: InMemoryStorage) -> None:
    lead_id = await _submit(authed)
    res = await authed.get(f"/api/v1/leads/{lead_id}/resume")
    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "cv.pdf"
    assert body["expiresIn"] == 300
    [key] = storage.objects
    assert key in body["url"]
