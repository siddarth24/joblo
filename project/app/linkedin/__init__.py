from flask import Blueprint

linkedin_bp = Blueprint("linkedin", __name__, url_prefix="/linkedin")

from . import routes  # noqa: E402, F401
