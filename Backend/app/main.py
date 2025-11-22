from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from db.session import init_db
from api.admin.routes_admin import router as admin_router
from api.client.routes_client import router as client_router

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-vehicle shuttle tracking system with admin and client APIs",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin_router, prefix="/api")
app.include_router(client_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print("✅ Database initialized")
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"📍 Admin endpoints: /api/admin/*")
    print(f"📍 Client endpoints: /api/client/*")


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
