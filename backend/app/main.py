from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine
from .models import Base
from .routers import audit, auth, consoles, dashboard, exports, groups, monitor, network, recordings, recordings_ws, setup, sources, status, storage, templates, users
from .routers.monitor import cleanup as cleanup_monitor_pcs


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cleanup_monitor_pcs()
    await engine.dispose()


app = FastAPI(
    title="Basin",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(setup.router)
app.include_router(status.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(storage.router)
app.include_router(network.router)
app.include_router(groups.router)
app.include_router(templates.router)
app.include_router(consoles.router)
app.include_router(recordings.router)
app.include_router(recordings_ws.router)
app.include_router(monitor.router)
app.include_router(dashboard.router)
app.include_router(exports.router)
app.include_router(audit.router)
