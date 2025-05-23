from celery import Celery
import os

# It's common to name the celery app module based on the project or the main app module name
# For Joblo, let's assume the Flask app object is created by a factory in project.app

# Globally instantiated Celery application
# Basic configuration can be done here, or rely on environment variables
# The main configuration will be applied by the Flask app factory.
celery = Celery(
    __name__, # Default name, can be customized
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["project.tasks"] # Modules to import when worker starts
)

# Optional: Set some default configurations directly if not overridden by Flask app
celery.conf.update(
    task_serializer=os.environ.get("CELERY_TASK_SERIALIZER", "json"),
    result_serializer=os.environ.get("CELERY_RESULT_SERIALIZER", "json"),
    accept_content=os.environ.get("CELERY_ACCEPT_CONTENT", "json").split(","),
    timezone=os.environ.get("CELERY_TIMEZONE", "UTC"),
    broker_connection_retry_on_startup=True,
)

def configure_celery_app(app, celery_instance):
    """
    Configures an existing Celery application instance with settings from a Flask app.
    """
    celery_config = {
        key: value
        for key, value in app.config.items()
        if key.startswith("CELERY_")
    }
    # Ensure broker and backend URLs from Flask config take precedence
    celery_config["broker_url"] = app.config.get(
        "CELERY_BROKER_URL", celery_instance.conf.broker_url
    )
    celery_config["result_backend"] = app.config.get(
        "CELERY_RESULT_BACKEND", celery_instance.conf.result_backend
    )
    # Ensure 'include' from Flask config can extend or override
    celery_config["include"] = app.config.get(
        "CELERY_INCLUDE", celery_instance.conf.include
    )
    if not celery_config["include"]:
        celery_config["include"] = ["project.tasks"] # Default if not set in Flask

    celery_instance.conf.update(celery_config)

    # Subclass Task to automatically push Flask app context
    class ContextTask(celery_instance.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery_instance.Task = ContextTask
    return celery_instance

# The global 'celery' instance is now defined above.
# The Flask app factory will import this global 'celery' and call 'configure_celery_app'.

# Initialize Celery app globally for worker discovery, but configure it via factory
# This allows 'celery -A project.celery_app.celery worker' to work,
# assuming the Flask app is created and passed to create_celery_app when the app runs.
# However, for factory pattern with Flask, direct global instantiation might be tricky.
# A common pattern is to have a celery.py that imports the task modules.

# For now, let's create a default celery instance that can be configured by the Flask app factory.
# The Flask app factory (`create_app` in `project/app/__init__.py`) will call `create_celery_app`.

# This global instance `celery` can be imported by tasks.py, but its config
# will be finalized when create_app calls create_celery_app(flask_app_instance).
# This is a bit of a hybrid approach.

# A cleaner way might be to NOT have a global celery object here, and have the flask factory
# create and store it. Tasks would then be defined using a deferred celery app proxy or by
# importing the configured celery instance from the flask app itself (if possible).

# Let's defer the global `celery = create_celery_app()` for now and assume
# `create_celery_app` is called from `project/app/__init__.py` and the instance is stored on the Flask app.
# Tasks will be defined in a separate `project/tasks.py` module.

# Instantiate a global Celery app object using the factory.
# The Flask app factory (create_app) will later configure this instance.
