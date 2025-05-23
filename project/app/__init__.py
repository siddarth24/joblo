import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from flask_cors import CORS
import redis

# Assuming config.py is in the parent directory of 'app' (i.e., in 'project')
from ..config import Config
from .utils import ensure_directories_exist
# Import the global celery instance and the configuration function
from ..celery_app import celery as global_celery_app, configure_celery_app


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure the global Celery instance with the Flask app context
    configure_celery_app(app, global_celery_app)
    app.celery_app = global_celery_app  # Store a reference to the configured global instance
    app.logger.info("Celery application initialized and configured with Flask app.")

    # Initialize Redis Client
    try:
        app.redis_client = redis.StrictRedis(
            host=app.config.get("REDIS_HOST", "localhost"),
            port=app.config.get("REDIS_PORT", 6379),
            db=app.config.get("REDIS_DB", 0),
            password=app.config.get(
                "REDIS_PASSWORD"
            ),  # Will be None if not set, which is fine for no-auth Redis
            decode_responses=False,  # Tasks expect bytes for direct JSON loading/pickling at times
        )
        app.redis_client.ping()  # Verify connection
        app.logger.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(f"Could not connect to Redis: {e_redis}", exc_info=True)
        app.redis_client = None  # Ensure it's None if connection fails
    except Exception as e_redis_other:
        app.logger.error(
            f"An unexpected error occurred during Redis initialization: {e_redis_other}",
            exc_info=True,
        )
        app.redis_client = None

    # Initialize External Service Clients
    try:
        from .clients.openai_client import OpenAIClient

        app.openai_client = OpenAIClient(
            api_key=app.config["OPENAI_API_KEY"],
            model_name=app.config["LLM_MODEL_NAME"],
            temperature=app.config["LLM_TEMPERATURE"],
            max_tokens=app.config["LLM_MAX_TOKENS"],
            top_p=app.config["LLM_TOP_P"],
        )
        app.logger.info("OpenAIClient initialized.")
    except KeyError as e_key:
        app.logger.error(
            f"OpenAIClient initialization failed: Missing config key {e_key}",
            exc_info=True,
        )
        app.openai_client = None  # Explicitly set to None on failure
    except Exception as e_openai:
        app.logger.error(
            f"OpenAIClient initialization failed: {e_openai}", exc_info=True
        )
        app.openai_client = None

    try:
        from .clients.cloudconvert_client import CloudConvertClient

        # Assuming CLOUDCONVERT_SANDBOX is an optional config, defaulting to False
        sandbox = app.config.get("CLOUDCONVERT_SANDBOX", False)
        app.cloudconvert_client = CloudConvertClient(
            api_key=app.config["CLOUDCONVERT_API_KEY"], sandbox=sandbox
        )
        app.logger.info("CloudConvertClient initialized.")
    except KeyError as e_key:
        app.logger.error(
            f"CloudConvertClient initialization failed: Missing config key {e_key}",
            exc_info=True,
        )
        app.cloudconvert_client = None
    except Exception as e_cc:
        app.logger.error(
            f"CloudConvertClient initialization failed: {e_cc}", exc_info=True
        )
        app.cloudconvert_client = None

    try:
        from .clients.scraper_client import ScraperClient

        # GROQ_API_KEY might be optional for the ScraperClient if not all paths require it
        app.scraper_client = ScraperClient(
            groq_api_key=app.config.get(
                "GROQ_API_KEY"
            )  # .get() allows it to be None if not set
        )
        app.logger.info("ScraperClient initialized.")
    except (
        Exception
    ) as e_scraper:  # ScraperClient import itself might fail if its deps fail
        app.logger.error(
            f"ScraperClient initialization failed: {e_scraper}", exc_info=True
        )
        app.scraper_client = None

    # Resolve project root to make folder paths absolute if they are relative
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )

    for folder_key in ["UPLOAD_FOLDER", "STATE_FOLDER", "LOG_DIR"]:
        folder_path = app.config.get(folder_key)
        if folder_path and not os.path.isabs(folder_path):
            app.config[folder_key] = os.path.join(project_root, folder_path)
        elif (
            not folder_path and folder_key == "LOG_DIR"
        ):  # Ensure LOG_DIR has a default if not set
            app.config["LOG_DIR"] = os.path.join(project_root, "logs")

    # Initialize logging
    log_dir = app.config["LOG_DIR"]
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                os.path.join(log_dir, "api_server.log"),  # Use resolved log_dir
                maxBytes=10485760,  # 10MB
                backupCount=5,
            ),
            logging.StreamHandler(),
        ],
    )
    app.logger.setLevel(logging.INFO)  # Ensure app logger also respects this level
    # You might want to remove Flask's default handlers if they conflict or add noise
    # for handler in list(app.logger.handlers):
    #     app.logger.removeHandler(handler)
    # for handler in logging.getLogger().handlers:
    #      app.logger.addHandler(handler)

    app.logger.info("Joblo API starting up...")

    # Initialize CORS
    cors_origins = app.config.get("CORS_ORIGINS", [])
    if not cors_origins and cors_origins != "*":  # Check if empty list and not wildcard
        app.logger.warning(
            "CORS_ORIGINS is not configured or empty, CORS might be restrictive or disabled depending on environment."
        )
        # Defaulting to an empty list is often a secure default (no origins allowed)
        # If you need a default for development, you could set it here, e.g., ['http://localhost:3000']
        # For now, an empty list means Flask-CORS won't add the ACAO header unless an origin matches.

    CORS(
        app,
        resources={
            r"/*": {
                "origins": cors_origins,
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
            }
        },
    )
    app.logger.info(f"CORS initialized. Allowed origins: {app.config['CORS_ORIGINS']}")

    # Ensure required directories exist using the absolute paths
    ensure_directories_exist(
        app
    )  # ensure_directories_exist should use app.config paths
    app.logger.info("Checked/created required directories.")

    # Langchain Tracing Configuration Note
    # Langchain auto-configures tracing if LANGCHAIN_API_KEY and LANGCHAIN_TRACING_V2="true" are set in environment.
    # Additional vars like LANGCHAIN_ENDPOINT and LANGCHAIN_PROJECT can also be set in env.
    if (
        os.environ.get("LANGCHAIN_API_KEY")
        and os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    ):
        app.logger.info(
            "Langchain Tracing is expected to be active based on environment variables."
        )
    else:
        app.logger.info(
            "Langchain Tracing is not expected to be active or LANGCHAIN_API_KEY is missing."
        )

    # Register blueprints
    from .main import main_bp

    app.register_blueprint(main_bp)

    from .linkedin import linkedin_bp

    app.register_blueprint(linkedin_bp)

    from .processing import processing_bp

    app.register_blueprint(processing_bp)

    app.logger.info("Blueprints registered.")

    # Register global error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 error: {request.path} - {error}")
        return jsonify({"success": False, "error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        app.logger.warning(f"405 error: {request.method} {request.path} - {error}")
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def request_entity_too_large_error(error):
        app.logger.warning(f"413 error: File too large at {request.path} - {error}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"The file is too large. Maximum allowed size is {app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)}MB",
                }
            ),
            413,
        )

    # A more general error handler for unhandled exceptions (though endpoint_metrics also handles some)
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        # If it's an HTTPException, re-raise it to let Flask handle it or use its response
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e
        # For other exceptions, return a generic 500
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected internal server error occurred.",
                }
            ),
            500,
        )

    app.logger.info("Global error handlers registered.")
    app.logger.info(
        f"Joblo API configured. UPLOAD_FOLDER: {app.config.get('UPLOAD_FOLDER')}, STATE_FOLDER: {app.config.get('STATE_FOLDER')}, LOG_DIR: {app.config.get('LOG_DIR')}"
    )

    return app
