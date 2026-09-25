"""The web client is generated from apps/web/openapi.json. If the API's schema changes without
regenerating it (`make generate-client`), this fails."""

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[2] / "web" / "openapi.json"


def test_openapi_matches_web_client_snapshot() -> None:
    assert SNAPSHOT.exists(), "run `make generate-client`"
    committed = json.loads(SNAPSHOT.read_text())
    current = json.loads(json.dumps(app.openapi()))
    assert current == committed, "API schema changed: run `make generate-client` and commit the result"
