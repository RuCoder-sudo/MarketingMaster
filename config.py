import os

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get("SESSION_SECRET", "dev-secret-key")
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///social_monitoring.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Application settings
    MAX_PROJECTS = 5
    DEFAULT_SEARCH_INTERVAL = 3600  # Default search interval in seconds (1 hour)
    MAX_RESULTS_PER_PAGE = 10
    
    # Logging settings
    LOG_LEVEL = "DEBUG"
