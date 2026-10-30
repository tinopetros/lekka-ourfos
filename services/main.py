import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from common import execution_id
from integrations import mifos
from routers import accounts, corrections, forms, requisitions, syncs


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


@app.middleware("http")
async def tag_logs(request: Request, call_next):
    execution_id.set(request.headers.get("x-execution-id"))
    return await call_next(request)
