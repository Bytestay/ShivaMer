from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from converter import to_mermaid

SITE_ORIGIN = "https://shivamer.bytestay.pt"
DEV_ORIGINS = ["http://localhost:5173", "http://localhost:8080"]
# 20_000 characters of code is the semantic limit; this only bounds what is buffered.
MAX_BODY_BYTES = 64 * 1024


def is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development") == "production"


def allowed_origins(production: bool) -> list[str]:
    configured = os.environ.get("ALLOWED_ORIGINS")
    if configured:
        origins = [o.strip() for o in configured.split(",") if o.strip()]
    else:
        origins = [SITE_ORIGIN]
    if production:
        return [o for o in origins if not o.startswith("http://localhost")]
    return origins + [o for o in DEV_ORIGINS if o not in origins]


class BodyLimitMiddleware:
    """Reject bodies above the limit with 413 before they are buffered."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def _too_large(self, send):
        body = b'{"detail":"Request body too large."}'
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = self.max_bytes + 1
                if declared > self.max_bytes:
                    return await self._too_large(send)
        received = 0
        responded = False

        async def limited_receive():
            nonlocal received, responded
            if responded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Answer now and tell the app the client is gone, so nothing more is buffered.
                    responded = True
                    await self._too_large(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if not responded:
                await send(message)

        await self.app(scope, limited_receive, guarded_send)


class ConvertReq(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)

class ConvertResp(BaseModel):
    mermaid: str


def make_app(production: bool) -> FastAPI:
    # Interactive docs load Swagger UI/ReDoc from a third-party CDN: dev only.
    docs = {} if not production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="ShivaMer API", **docs)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(production),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(BodyLimitMiddleware)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/")
    def root():
        return {"message": "ShivaMer API. Use /convert (POST)."}

    @app.post("/convert", response_model=ConvertResp)
    def convert(req: ConvertReq):
        try:
            return ConvertResp(mermaid=to_mermaid(req.code))
        except SyntaxError as e:
            raise HTTPException(status_code=400, detail=f"SyntaxError: {e.msg} (line {e.lineno})") from e
        except (RecursionError, MemoryError):
            raise HTTPException(status_code=400, detail="Code is too deeply nested to convert.") from None

    return app


app = make_app(is_production())
