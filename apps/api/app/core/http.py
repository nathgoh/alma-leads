from fastapi import HTTPException, Request, status


async def require_json(request: Request) -> None:
    """JSON-only bodies force a CORS preflight for any cross-origin caller (CSRF depth)."""
    content_type = request.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
