"""ourfos-api: what the UI reads, and the UI itself, from one origin.

Run as `uvicorn api.main:app`, from the same image as ourfos-services. It imports none of what posts or sends: no
Mifos, no Gmail, no model.
"""

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from common import log

from . import routes

# The built UI: web/dist, copied in by the image's build. Absent locally, where Vite serves it
STATIC = Path(os.environ.get("STATIC_DIR", Path(__file__).parent.parent / "static"))

app = FastAPI(title="ourfos-api")
app.include_router(routes.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Every request: who, what, how it ended, and how long it took."""
    start, status = time.monotonic(), 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if request.url.path.startswith("/api/"):
            log(
                "request",
                "ERROR" if status >= 500 else "INFO",
                user=getattr(request.state, "user", None),
                method=request.method,
                path=request.url.path,
                status=status,
                ms=round((time.monotonic() - start) * 1000),
            )


if (STATIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str):
        """The UI's own files, and index.html for every route of its own, which React Router takes from there."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        file = (STATIC / path).resolve()
        if path and file.is_file() and file.is_relative_to(STATIC.resolve()):
            return FileResponse(file)
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
