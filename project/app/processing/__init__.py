from flask import Blueprint

processing_bp = Blueprint("processing", __name__, url_prefix="/processing")

from . import routes  # noqa: E402, F401
