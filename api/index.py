import os
import sys
from pathlib import Path
from fastapi import Request

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

data_dir = root_dir / "data" / "generated"
if data_dir.exists():
    os.environ["LOCAL_DATA_DIR"] = str(data_dir.resolve())

# In serverless environments like Vercel, root filesystem is read-only; use /tmp for state & runtime dirs
if os.environ.get("VERCEL") or not os.name == "nt":
    os.environ.setdefault("STATE_DIR", "/tmp/.state")
    os.environ.setdefault("METERLESS_WORLD_DIR", "/tmp/meterless_world")

# This function only serves the OFFLINE fallback (/offline-api): sample mode, bundled data, no live services, whatever the project env says.
os.environ["SAMPLE_MODE"] = "true"
os.environ["ZETARIS_ENABLED"] = "false"
os.environ["NIGHTSHIFT_API_KEY"] = ""
os.environ["NIGHTSHIFT_API_KEY_FILE"] = ""

from app.main import app
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount frontend/dist static files for the UI
frontend_dist = root_dir / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def catch_all(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

@app.middleware("http")
async def route_middleware(request: Request, call_next):
    route = request.query_params.get("_route")
    if route:
        request.scope["path"] = f"/api/{route.lstrip('/')}"
    return await call_next(request)
