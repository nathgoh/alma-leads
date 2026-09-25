"""Print the OpenAPI schema (the API ↔ web contract): `python -m app.openapi_dump > openapi.json`."""

import json
import sys

from app.main import app

if __name__ == "__main__":
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
