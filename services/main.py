from fastapi import FastAPI

from routers import mifos, requisitions, workspace

app = FastAPI(title="ourfos-services")
app.include_router(requisitions.router)
app.include_router(workspace.router)
app.include_router(mifos.router)
