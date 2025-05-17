from flask import jsonify
from . import main_bp
from ..utils import endpoint_metrics # Assuming utils.py is one level up

@main_bp.route('/health', methods=['GET'])
@endpoint_metrics
def health_check():
    \"\"\"Health check endpoint to verify API is running.\"\"\"
    return jsonify({"success": True, "status": "ok"}), 200 