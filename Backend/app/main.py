from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.logger import logger, log_error
from app.db.session import init_db
from app.api.admin.routes_admin import router as admin_router
from app.api.client.routes_client import router as client_router
from app.api.client.routes_eta import router as eta_router

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-vehicle shuttle tracking system with admin and client APIs",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
# Note: When allow_credentials=True, allow_origins cannot be ["*"]
# Either use specific origins or set allow_credentials=False
print(f"🔍 CORS Configuration:")
print(f"   CORS_ORIGINS from .env: {settings.CORS_ORIGINS}")
print(f"   Parsed origins list: {settings.cors_origins_list}")

if settings.cors_origins_list == ["*"]:
    # For development: allow all origins without credentials
    print(f"   Mode: Wildcard (allow_credentials=False)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
else:
    # For production: specific origins with credentials
    print(f"   Mode: Specific origins (allow_credentials=True)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

print(f"✅ CORS middleware configured successfully")


# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.warning(
        f"HTTP {exc.status_code}: {request.method} {request.url.path} - {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with user-friendly messages"""
    errors = exc.errors()
    logger.warning(f"Validation error: {request.method} {request.url.path} - {errors}")
    
    # Format error messages
    formatted_errors = []
    for error in errors:
        field = " -> ".join(str(x) for x in error["loc"])
        formatted_errors.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request data",
            "errors": formatted_errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unexpected errors"""
    log_error(
        f"{request.method} {request.url.path}",
        exc,
        "system"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__ if settings.DEBUG else None
        }
    )


# Include routers
app.include_router(admin_router, prefix="/api")
app.include_router(client_router, prefix="/api")
app.include_router(eta_router, prefix="/api/client")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        logger.info("=" * 60)
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info("=" * 60)
        
        init_db()
        logger.info("✅ Database initialized successfully")
        logger.info(f"✅ Debug mode: {settings.DEBUG}")
        logger.info(f"📍 Admin endpoints: /api/admin/*")
        logger.info(f"📍 Client endpoints: /api/client/*")
        logger.info(f"📍 ETA endpoints: /api/client/eta/*")
        logger.info(f"📄 API documentation: /docs")
        logger.info("=" * 60)
        
        # Console output for quick visibility
        print("✅ Database initialized")
        print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started")
        print(f"📍 Admin endpoints: /api/admin/*")
        print(f"📍 Client endpoints: /api/client/*")
        print(f"📍 ETA endpoints: /api/client/eta/*")
        print(f"📄 Logs: logs/shuttle_tracker_*.log")
        
    except Exception as e:
        logger.error(f"Startup failed: {type(e).__name__} - {str(e)}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("=" * 60)
    logger.info(f"Shutting down {settings.APP_NAME}")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "endpoints": {
            "admin": "/api/admin",
            "client": "/api/client",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
