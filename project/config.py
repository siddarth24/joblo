import os

class Config:
    \"\"\"Configuration for the Flask application.\"\"\"
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]
    PORT = int(os.environ.get("PORT", 5500))
    HOST = os.environ.get("HOST", "0.0.0.0")
    # STATE_FOLDER = os.environ.get("STATE_FOLDER", "linkedin_states") # Consider making this path absolute or relative to instance_path
    # UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads") # Same as above
    # ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
    # MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit for uploads

    # It's good practice to also define other constants here if they are configurable
    # e.g., API keys if not handled solely by joblo_core.py's load_dotenv
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
    # GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    # CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")

    # For Blueprints, it's also useful to have:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    LOG_DIR = os.environ.get('LOG_DIR') or 'logs'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    STATE_FOLDER = os.environ.get('STATE_FOLDER') or 'linkedin_states'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'md', 'json'}
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    CLOUDCONVERT_API_KEY = os.environ.get('CLOUDCONVERT_API_KEY')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    
    CORS_ORIGINS_STR = os.environ.get('CORS_ORIGINS') or ''
    if CORS_ORIGINS_STR == "*":
        CORS_ORIGINS = "*"
    elif CORS_ORIGINS_STR:
        CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(',')]
    else:
        CORS_ORIGINS = []

    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

    # Celery Configuration
    CELERY_BROKER_URL: str = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND: str = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/2'
    CELERY_ACCEPT_CONTENT: list = ['json', 'pickle'] # Added pickle for more complex objects if needed, ensure worker also accepts
    CELERY_TASK_SERIALIZER: str = 'pickle' # Changed from json to pickle
    CELERY_RESULT_SERIALIZER: str = 'pickle' # Changed from json to pickle
    CELERY_TIMEZONE: str = 'UTC'
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP: bool = True # For robust startup

    # LLM Configuration
    LLM_MODEL_NAME: str = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    LLM_TEMPERATURE: float = float(os.environ.get('LLM_TEMPERATURE', 0.7))
    LLM_MAX_TOKENS: int = int(os.environ.get('LLM_MAX_TOKENS', 3000))
    LLM_TOP_P: float = float(os.environ.get('LLM_TOP_P', 1.0))

    # Cache Configuration
    CACHE_LLM_RESPONSES: bool = os.environ.get('CACHE_LLM_RESPONSES', 'True').lower() in ('true', '1', 't')
    LLM_CACHE_TTL_SECONDS: int = int(os.environ.get('LLM_CACHE_TTL_SECONDS', 86400)) # Default 24 hours

    CACHE_SCRAPER_RESPONSES: bool = os.environ.get('CACHE_SCRAPER_RESPONSES', 'True').lower() in ('true', '1', 't')
    SCRAPER_CACHE_TTL_SECONDS: int = int(os.environ.get('SCRAPER_CACHE_TTL_SECONDS', 3600)) # Default 1 hour

    # Feature Flags (example)
    ENABLE_RAG_FEATURE: bool = os.environ.get('ENABLE_RAG_FEATURE', 'True').lower() in ('true', '1', 't')

    # Optional: Print warnings if essential API keys are not set
    # These checks can also be done at the point of use or during app startup
    # if not OPENAI_API_KEY:
    #     print("Warning: OPENAI_API_KEY is not set in environment variables.")
    # if not CLOUDCONVERT_API_KEY:
    #     print("Warning: CLOUDCONVERT_API_KEY is not set in environment variables.")
    # if not GROQ_API_KEY:
    #     print("Warning: GROQ_API_KEY is not set in environment variables.") 