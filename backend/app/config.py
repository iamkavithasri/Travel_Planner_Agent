from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Keys
    GROQ_API_KEY: str
    OPENTRIPMAP_API_KEY: str = ""  # Optional - OSM will be used as primary
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"]
    
    # LLM Config
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.7
    MAX_REPLANNING_ITERATIONS: int = 3
    
    # OSM Config
    OSM_SEARCH_RADIUS: int = 5000  # meters
    OSM_MAX_RESULTS: int = 150
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()