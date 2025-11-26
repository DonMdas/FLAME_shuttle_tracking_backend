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
    
    # CORS
    CORS_ORIGINS: str
    
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
