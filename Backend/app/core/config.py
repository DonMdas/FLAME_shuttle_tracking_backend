from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application configuration settings loaded from .env file"""
    
    # Application
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    API_BASE_URL: str
    
    # Security
    SECRET_KEY: str  # Required - no default for security
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # Admin credentials (loaded from .env)
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    
    # Database
    DATABASE_URL: str
    
    # EERA GPS API
    EERA_BASE_URL: str
    EERA_ENDPOINT: str
    EERA_API_KEY: str  # Single API key for all vehicles
    
    # GPS Configuration
    GPS_DATA_STALE_THRESHOLD: int   # Seconds - data older than this is considered stale
    VEHICLE_SYNC_INTERVAL: int   # Seconds - sync vehicle list every 5 minutes
    DESTINATION_PROXIMITY_THRESHOLD: int  # Meters - distance threshold to auto-deactivate schedule
    
    # CORS
    CORS_ORIGINS: str
    
    #OSRM_BASE_URL
    OSRM_BASE_URL : str
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
