"""Main FastAPI application for the smoker controller."""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import settings
from db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    create_db_and_tables()
    
    # Start WebSocket broadcasting
    from ws.manager import start_websocket_broadcasting
    await start_websocket_broadcasting()
    
    yield
    
    # Shutdown
    from ws.manager import stop_websocket_broadcasting
    await stop_websocket_broadcasting()


# Create FastAPI app
app = FastAPI(
    title="Smoker Controller API",
    description="Raspberry Pi smoker controller with web GUI",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
from api.routers import control, readings, settings as settings_router, alerts, export, smokes, thermocouples
app.include_router(control.router, prefix="/api/control", tags=["control"])
app.include_router(readings.router, prefix="/api/readings", tags=["readings"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(smokes.router, prefix="/api/smokes", tags=["smokes"])
app.include_router(thermocouples.router, prefix="/api/thermocouples", tags=["thermocouples"])

# Include WebSocket router
from ws.manager import router as ws_router
app.include_router(ws_router, tags=["websocket"])

# Serve static files in production
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
