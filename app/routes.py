from flask import Blueprint, jsonify, request
from app.services.cosmos_service import CosmosService
from app.services.blob_service import BlobService

bp = Blueprint("routes", __name__)

ALLOWED_STATUSES = {"todo", "in_progress", "done"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}

@bp.route("/")
def home():
    return jsonify({"message": "Team Task Manager API running"})


@bp.route("/tasks", methods=["POST"])
def create_task():
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    file = request.files.get("file")

    if "title" not in data:
        return jsonify({"error": "title is required"}), 400

    status = data.get("status", "todo")
    priority = data.get("priority", "medium")

    if status not in ALLOWED_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    if priority not in ALLOWED_PRIORITIES:
        return jsonify({"error": "invalid priority"}), 400

    file_url = None
    if file:
        blob = BlobService()
        file_url = blob.upload_file(file)

    task_data = {
        "title": data["title"],
        "description": data.get("description", ""),
        "status": status,
        "priority": priority,
        "deadline": data.get("deadline", ""),
        "file_url": file_url
    }

    cosmos = CosmosService()
    created = cosmos.create_task(task_data)
    return jsonify(created), 201


@bp.route("/tasks", methods=["GET"])
def list_tasks():
    cosmos = CosmosService()
    return jsonify(cosmos.list_tasks())


@bp.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    cosmos = CosmosService()
    try:
        return jsonify(cosmos.get_task(task_id))
    except Exception:
        return jsonify({"error": "task not found"}), 404


@bp.route("/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "no update data provided"}), 400

    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    if "priority" in data and data["priority"] not in ALLOWED_PRIORITIES:
        return jsonify({"error": "invalid priority"}), 400

    cosmos = CosmosService()
    try:
        return jsonify(cosmos.update_task(task_id, data))
    except Exception:
        return jsonify({"error": "task not found"}), 404


@bp.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    cosmos = CosmosService()
    try:
        cosmos.delete_task(task_id)
        return jsonify({"deleted": True})
    except Exception:
        return jsonify({"error": "task not found"}), 404
