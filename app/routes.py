# app/routes.py
from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename

from app.services.cosmos_service import CosmosService
from app.services.blob_service import BlobService
from app.utils.api import ok, fail

bp = Blueprint("routes", __name__)

TASK_FIELDS = {"id", "title", "description", "status", "priority", "deadline", "file_url"}

ALLOWED_STATUSES = {"todo", "in_progress", "done"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}
ALLOWED_SORT_FIELDS = {"title", "status", "priority", "deadline"}


# -------------------------
# Helpers
# -------------------------

def serialize_task(item: dict) -> dict:
    return {k: item.get(k) for k in TASK_FIELDS}


def parse_pagination(args):
    try:
        limit = int(args.get("limit", 20))
        offset = int(args.get("offset", 0))
    except ValueError:
        return None, None, fail("Invalid pagination values. Use integers.", 400)

    if limit < 1 or limit > 100:
        return None, None, fail("limit must be between 1 and 100.", 400)
    if offset < 0:
        return None, None, fail("offset must be >= 0.", 400)

    return limit, offset, None


def validate_filters(args):
    status = args.get("status")
    priority = args.get("priority")

    if status and status not in ALLOWED_STATUSES:
        return None, None, fail(f"Invalid status. Allowed: {sorted(ALLOWED_STATUSES)}", 400)

    if priority and priority not in ALLOWED_PRIORITIES:
        return None, None, fail(f"Invalid priority. Allowed: {sorted(ALLOWED_PRIORITIES)}", 400)

    return status, priority, None


def validate_sorting(args):
    sort = args.get("sort")
    order = args.get("order", "asc")

    if sort and sort not in ALLOWED_SORT_FIELDS:
        return None, None, fail(f"Invalid sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}", 400)

    if order not in {"asc", "desc"}:
        return None, None, fail("order must be 'asc' or 'desc'.", 400)

    return sort, order, None


# -------------------------
# Simple token auth
# -------------------------

def require_api_token():
    token = current_app.config.get("API_TOKEN")

    # If no token configured → allow (local dev mode)
    if not token:
        return None

    header = request.headers.get("Authorization", "")

    if not header.startswith("Bearer "):
        return fail("Missing or invalid Authorization header.", 401)

    incoming = header.split(" ", 1)[1].strip()

    if incoming != token:
        return fail("Unauthorized.", 401)

    return None


# -------------------------
# Routes
# -------------------------

@bp.route("/")
def home():
    return ok({"message": "Team Task Manager API running"})


@bp.route("/tasks", methods=["POST"])
def create_task():
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    title = (data.get("title") or "").strip()
    if not title:
        return fail("title is required.", 400)

    status = data.get("status", "todo")
    priority = data.get("priority", "medium")

    if status not in ALLOWED_STATUSES:
        return fail(f"Invalid status. Allowed: {sorted(ALLOWED_STATUSES)}", 400)

    if priority not in ALLOWED_PRIORITIES:
        return fail(f"Invalid priority. Allowed: {sorted(ALLOWED_PRIORITIES)}", 400)

    task = {
        "title": title,
        "description": (data.get("description") or "").strip(),
        "status": status,
        "priority": priority,
        "deadline": data.get("deadline"),
        "file_url": None,
    }

    try:
        cosmos = CosmosService()
        created = cosmos.create_task(task)
        return ok(serialize_task(created), message="Task created.", status=201)

    except Exception:
        current_app.logger.exception("Failed to create task")
        return fail("Internal server error.", 500)


@bp.route("/tasks", methods=["GET"])
def list_tasks():
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    status, priority, err = validate_filters(request.args)
    if err:
        return err

    limit, offset, err = parse_pagination(request.args)
    if err:
        return err

    sort, order, err = validate_sorting(request.args)
    if err:
        return err

    try:
        cosmos = CosmosService()

        # Preferred: implement filtering/pagination/sorting inside Cosmos
        items, total = cosmos.list_tasks(
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order
        )

    except AttributeError:
        # Fallback (in-memory filtering for demo projects)
        cosmos = CosmosService()
        all_items = cosmos.get_all_tasks()

        filtered = all_items

        if status:
            filtered = [t for t in filtered if t.get("status") == status]

        if priority:
            filtered = [t for t in filtered if t.get("priority") == priority]

        if sort:
            reverse = order == "desc"
            filtered.sort(key=lambda x: x.get(sort) or "", reverse=reverse)

        total = len(filtered)
        items = filtered[offset:offset + limit]

    except Exception:
        current_app.logger.exception("Failed to list tasks")
        return fail("Internal server error.", 500)

    return ok({
        "items": [serialize_task(i) for i in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": (offset + limit) < total
        },
        "filters": {
            "status": status,
            "priority": priority
        },
        "sorting": {
            "sort": sort,
            "order": order
        }
    })


@bp.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    try:
        cosmos = CosmosService()
        item = cosmos.get_task(task_id)

        if not item:
            return fail("Task not found.", 404)

        return ok(serialize_task(item))

    except Exception:
        current_app.logger.exception("Failed to get task")
        return fail("Internal server error.", 500)


@bp.route("/tasks/<task_id>", methods=["PATCH"])
def update_task(task_id):
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    allowed_updates = {"title", "description", "status", "priority", "deadline"}
    updates = {k: v for k, v in data.items() if k in allowed_updates}

    if not updates:
        return fail("No valid fields provided for update.", 400)

    if "status" in updates and updates["status"] not in ALLOWED_STATUSES:
        return fail(f"Invalid status. Allowed: {sorted(ALLOWED_STATUSES)}", 400)

    if "priority" in updates and updates["priority"] not in ALLOWED_PRIORITIES:
        return fail(f"Invalid priority. Allowed: {sorted(ALLOWED_PRIORITIES)}", 400)

    try:
        cosmos = CosmosService()
        updated = cosmos.update_task(task_id, updates)

        if not updated:
            return fail("Task not found.", 404)

        return ok(serialize_task(updated), message="Task updated.")

    except Exception:
        current_app.logger.exception("Failed to update task")
        return fail("Internal server error.", 500)


@bp.route("/tasks/<task_id>/upload", methods=["POST"])
def upload_file(task_id):
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    if "file" not in request.files:
        return fail("Missing file field 'file'.", 400)

    f = request.files["file"]

    if not f.filename:
        return fail("Empty filename.", 400)

    filename = secure_filename(f.filename)

    try:
        blob = BlobService()
        file_url = blob.upload_file(f, filename)

        cosmos = CosmosService()
        updated = cosmos.update_task(task_id, {"file_url": file_url})

        if not updated:
            return fail("Task not found.", 404)

        return ok(serialize_task(updated), message="File uploaded.")

    except Exception:
        current_app.logger.exception("Failed to upload file")
        return fail("Internal server error.", 500)
