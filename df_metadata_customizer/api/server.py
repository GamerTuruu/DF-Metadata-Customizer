"""REST API Server Entry Point using FastAPI."""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.logging import RichHandler

from df_metadata_customizer.api import routes_files, routes_presets
from df_metadata_customizer.api.models import StatusResponse

# Setup logging
logging_handler = RichHandler(
    show_time=True,
    show_level=True,
    show_path=False,
    markup=False,
    rich_tracebacks=True,
)
logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[logging_handler])

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Database Formatter API",
    description="REST API for MP3 metadata management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes_files.router)
app.include_router(routes_presets.router)


@app.get("/health", response_model=StatusResponse)
async def health_check() -> StatusResponse:
    """Health check endpoint."""
    return StatusResponse(success=True, message="API is healthy")


@app.get("/", response_model=dict)
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "Database Formatter API",
        "version": "2.0.0",
        "description": "REST API for MP3 metadata management",
        "docs": "/docs",
        "redoc": "/redoc",
    }


def main() -> None:
    """Launch the FastAPI server."""
    logger.info("🚀 Starting API server")
    logger.info("📡 API will be available at http://localhost:8000")
    logger.info("📖 API documentation: http://localhost:8000/docs")
    logger.info("📚 ReDoc documentation: http://localhost:8000/redoc")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
