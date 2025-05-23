# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP wsgi:app
ENV FLASK_ENV development
ENV PYTHONPATH /app
# Note: APP_SETTINGS should be set in docker-compose.yml or runtime environment

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by Python packages
# Example: apt-get update && apt-get install -y some-package
# For Joblo, Pillow, OpenCV, pytesseract might need system libs.
# Tesseract needs tesseract-ocr. OpenCV might need libgl1-mesa-glx.
# pdf2image needs poppler-utils.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1-mesa-glx \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 5500 available to the world outside this container (or your app's configured port)
# This should match what Gunicorn will bind to. The actual port mapping is done in docker-compose or docker run.
EXPOSE 5500

# Define the command to run the application using Gunicorn
# Ensure the number of workers is appropriate for your environment.
# The FLASK_APP environment variable is usually picked up by `flask run` but Gunicorn needs the module:app format.
# We use project.run:create_app() since create_app() is the factory.
# However, Gunicorn typically needs a direct app object. Let's assume run.py provides `app = create_app()`.
# If run.py just has `if __name__ == '__main__': app.run()`, Gunicorn needs a different entry or a small app.py.
# For now, assuming `project.run:app` where `app` is created by `create_app()` at module level in `run.py` or `wsgi.py`
# If `run.py` uses `if __name__ == '__main__':`, then gunicorn needs a different entry point like a `wsgi.py` file.
# Let's create a simple wsgi.py for Gunicorn if run.py is not suitable.

# Assuming run.py is structured to be callable by Gunicorn (e.g., app = create_app() is at top level)
# If not, a wsgi.py file might be better: `from project.app import create_app; app = create_app()`
# CMD ["gunicorn", "--bind", "0.0.0.0:5500", "project.run:app"] 
# Let's assume project/run.py is the entrypoint and it creates an app instance called 'app' globally.
# If using an app factory `create_app`, Gunicorn needs to call that. A common way is to have a wsgi.py:
# --- wsgi.py ---
# from project.app import create_app
# application = create_app()
# -----------------
# Then CMD would be `gunicorn --bind 0.0.0.0:5500 wsgi:application`

# For simplicity now, let's assume `project.run:app` is valid for Gunicorn (run.py defines `app = create_app()`)
# If project/run.py is just: `if __name__ == '__main__': app = create_app(); app.run(...)`
# then Gunicorn needs an app object. Let's check run.py structure. 
# Given current `run.py`, it uses `if __name__ == "__main__"`. We need a `wsgi.py`.

# Default command if not using Gunicorn for development/simplicity, though Gunicorn is better for prod.
# CMD ["python", "project/run.py"] 

# Recommended: Use Gunicorn for production. Create a wsgi.py for this.
# The command below assumes you will create a wsgi.py file in the project root.
CMD ["gunicorn", "--workers=2", "--threads=4", "--worker-class=gthread", "--timeout", "120", "--bind", "0.0.0.0:5500", "wsgi:application"] 