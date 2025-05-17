from celery import Celery
import os

# It's common to name the celery app module based on the project or the main app module name
# For Joblo, let's assume the Flask app object is created by a factory in project.app

def create_celery_app(flask_app=None):
    """
    Factory function to create and configure a Celery application.
    It can optionally be bound to a Flask application.
    """
    # If CELERY_BROKER_URL and CELERY_RESULT_BACKEND are set directly in the environment,
    # Celery can pick them up. Otherwise, they need to be passed in the config.
    # We will load them from the Flask app's config if available, or rely on Celery's defaults/env vars.

    celery = Celery(
        __name__, # Default name, can be customized e.g., 'joblo.tasks'
        # broker and backend will be configured via celery.conf.update or from Flask app config
    )

    if flask_app:
        # Update Celery config from Flask app config
        # Celery config keys are typically prefixed with CELERY_
        celery_config = {key: value for key, value in flask_app.config.items() if key.startswith('CELERY_')}
        # Celery expects keys without the CELERY_ prefix in its own config object sometimes.
        # For broker_url and result_backend, it's often direct.
        celery_config['broker_url'] = flask_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        celery_config['result_backend'] = flask_app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
        celery_config['include'] = ['project.tasks'] # List of modules to import when worker starts.
        # Add other Celery settings from Flask config as needed
        # For example: task_serializer, result_serializer, accept_content, timezone etc.
        celery_config['task_serializer'] = flask_app.config.get('CELERY_TASK_SERIALIZER', 'json')
        celery_config['result_serializer'] = flask_app.config.get('CELERY_RESULT_SERIALIZER', 'json')
        celery_config['accept_content'] = flask_app.config.get('CELERY_ACCEPT_CONTENT', ['json'])
        celery_config['timezone'] = flask_app.config.get('CELERY_TIMEZONE', 'UTC')
        celery_config['broker_connection_retry_on_startup'] = True

        celery.conf.update(celery_config)

        # Subclass Task to automatically push Flask app context
        class ContextTask(celery.Task):
            abstract = True
            def __call__(self, *args, **kwargs):
                with flask_app.app_context():
                    return super().__call__(*args, **kwargs)
        
        celery.Task = ContextTask
    else:
        # Fallback if no Flask app provided, rely on Celery picking up from env or defaults
        # This branch might be less common if Celery is tightly integrated with Flask.
        celery.conf.broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        celery.conf.result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
        celery.conf.include = ['project.tasks']
        celery.conf.task_serializer = os.environ.get('CELERY_TASK_SERIALIZER', 'json')
        celery.conf.result_serializer = os.environ.get('CELERY_RESULT_SERIALIZER', 'json')
        celery.conf.accept_content = os.environ.get('CELERY_ACCEPT_CONTENT', 'json').split(',') 
        celery.conf.timezone = os.environ.get('CELERY_TIMEZONE', 'UTC')
        celery.conf.broker_connection_retry_on_startup = True

    return celery

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