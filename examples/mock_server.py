"""Mock escrow/GraphQL-style backend used to exercise SchemaLock's example config.

Deliberately implements the *correct* contract by default. Set
MOCK_BREAK_CONTRACT=1 to flip a few responses into a broken contract, for
demonstrating that SchemaLock actually catches regressions.

Run: uvicorn examples.mock_server:app --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Escrow API")

BREAK = os.environ.get("MOCK_BREAK_CONTRACT") == "1"

ESCROWS = {
    "esc_123": {"id": "esc_123", "amount": 500, "status": "PENDING"},
}


def error_envelope(code: str, message: str) -> dict:
    body = {"error": True, "message": message, "code": code}
    if BREAK:
        # simulate envelope drift: rename "message" -> "msg"
        body = {"error": True, "msg": message, "code": code}
    return body


def is_authed(authorization: str | None) -> bool:
    return authorization == "Bearer valid-token"


@app.post("/escrows")
async def create_escrow(request: Request, authorization: str | None = Header(default=None)):
    if not is_authed(authorization):
        return JSONResponse(
            status_code=401, content=error_envelope("UNAUTHORIZED", "Missing or invalid token")
        )
    payload = await request.json()
    return JSONResponse(
        status_code=201,
        content={"id": "esc_new", "amount": payload.get("amount"), "status": "PENDING"},
    )


@app.get("/escrows/{escrow_id}")
async def get_escrow(escrow_id: str, authorization: str | None = Header(default=None)):
    if not is_authed(authorization):
        return JSONResponse(
            status_code=401, content=error_envelope("UNAUTHORIZED", "Missing or invalid token")
        )
    escrow = ESCROWS.get(escrow_id)
    if escrow is None:
        status = 200 if BREAK else 404  # simulate a leaked-existence auth/404 bug
        return JSONResponse(
            status_code=status, content=error_envelope("NOT_FOUND", "Escrow not found")
        )
    return escrow


@app.delete("/escrows/{escrow_id}")
async def delete_escrow(escrow_id: str, authorization: str | None = Header(default=None)):
    if not is_authed(authorization):
        return JSONResponse(
            status_code=401, content=error_envelope("UNAUTHORIZED", "Missing or invalid token")
        )
    escrow = ESCROWS.get(escrow_id)
    if escrow is None:
        return JSONResponse(
            status_code=404, content=error_envelope("NOT_FOUND", "Escrow not found")
        )
    if escrow["status"] != "PENDING":
        status = 400 if BREAK else 409  # simulate the 400-vs-409 contract bug
        return JSONResponse(
            status_code=status,
            content=error_envelope("INVALID_STATE", "Escrow is no longer pending"),
        )
    return Response(status_code=204)  # 204 must have no body, or it corrupts keep-alive framing


@app.post("/graphql")
async def graphql(request: Request, authorization: str | None = Header(default=None)):
    if not is_authed(authorization):
        return JSONResponse(
            status_code=401, content=error_envelope("UNAUTHORIZED", "Missing or invalid token")
        )
    payload = await request.json()
    query = payload.get("query", "")
    if "invalidField" in query:
        return JSONResponse(
            status_code=422,
            content=error_envelope("VALIDATION_ERROR", "Unknown field 'invalidField'"),
        )
    return JSONResponse(status_code=200, content={"data": {"escrow": ESCROWS["esc_123"]}})


@app.get("/health")
async def health():
    return {"status": "ok"}
