import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.auth import jwt

from common import execution_id
from integrations import mifos
from routers import accounts, actions, corrections, forms, requisitions, syncs

# What ourfos-api may call. Cloud Run lets any invoker reach every route, so the rest stay the workflow's here
API_MAY = {"/mifos/accounts"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In the background, so a slow Mifos never holds up a start
    threading.Thread(target=mifos.connect, daemon=True).start()
    yield


app = FastAPI(title="ourfos-services", lifespan=lifespan)
app.include_router(requisitions.router)
app.include_router(corrections.router)
app.include_router(forms.router)
app.include_router(syncs.router)
app.include_router(accounts.router)
app.include_router(actions.router)


@app.middleware("http")
async def tag_logs(request: Request, call_next):
    execution_id.set(request.headers.get("x-execution-id"))
    return await call_next(request)


@app.middleware("http")
async def api_reads_only(request: Request, call_next):
    api = os.environ.get("API_ACCOUNT")
    if api and caller(request) == api and request.url.path not in API_MAY:
        return JSONResponse({"detail": "ourfos-api may only read accounts here"}, status_code=403)
    return await call_next(request)


def caller(request: Request) -> str | None:
    """Who called, from their ID token. Cloud Run checked it before letting the request in, and replaces its signature,
    so only its claims are read here"""
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    try:
        return jwt.decode(token, verify=False).get("email")
    except ValueError:
        return None
