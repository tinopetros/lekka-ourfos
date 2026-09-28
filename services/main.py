from fastapi import FastAPI, Request

from common import execution_id
from routers import gmail, requisitions

app = FastAPI(title="ourfos-services")
app.include_router(requisitions.router)
app.include_router(gmail.router)


@app.middleware("http")
async def tag_logs(request: Request, call_next):
    execution_id.set(request.headers.get("x-execution-id"))
    return await call_next(request)
