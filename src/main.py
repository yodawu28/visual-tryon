"""
FastAPI application entry point.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from src.api.routes import health, privacy, analysis, generation, products
from src.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Virtual Try-On MVP API",
    description="Privacy-first virtual try-on system with face anonymization and semantic parsing",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc) if settings.debug else "Internal server error",
        },
    )


# Include routers
app.include_router(health.router)
app.include_router(privacy.router)
app.include_router(analysis.router)
app.include_router(generation.router)
app.include_router(generation.manual_router)
app.include_router(products.router)


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    logger.info("🚀 Starting Virtual Try-On MVP API...")
    logger.info(f"📍 Environment: {settings.environment}")
    logger.info(f"🔧 Debug mode: {settings.debug}")

    # Warm up models
    try:
        from src.modules.privacy_guard.face_detector import FaceDetector

        _ = FaceDetector()
        logger.info("✅ Face detector initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize face detector: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down Virtual Try-On MVP API...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1,  # Single worker cho ML models
    )
