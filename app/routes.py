from flask import Blueprint, jsonify

bp = Blueprint("routes", __name__)

@bp.route("/")
def home():
    return jsonify({"message": "Team Task Manager API running"})
