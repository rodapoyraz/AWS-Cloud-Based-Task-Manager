from flask import Blueprint, request, current_app, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename

from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.auth_models import User
from app.services.cosmos_service import CosmosService
from app.services.blob_service import BlobService
from app.services.email_service import EmailService
from app.utils.api import ok, fail

bp = Blueprint("routes", __name__)

# Fields returned to API callers / UI tables (intentionally hide owner_id + assignee_id by default)
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


def require_api_token():
    """
    Optional extra protection for API routes.
    If API_TOKEN is set, require Bearer token header even if user is logged in.
    """
    token = current_app.config.get("API_TOKEN")
    if not token:
        return None

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return fail("Missing or invalid Authorization header.", 401)

    incoming = header.split(" ", 1)[1].strip()
    if incoming != token:
        return fail("Unauthorized.", 401)

    return None


def can_view_task(task: dict, user_id: str) -> bool:
    """Owner OR assignee can view."""
    return task.get("owner_id") == user_id or task.get("assignee_id") == user_id


def can_edit_task(task: dict, user_id: str) -> bool:
    """Only owner can edit/delete/assign."""
    return task.get("owner_id") == user_id


def ensure_can_view(cosmos: CosmosService, task_id: str):
    task = cosmos.get_task(task_id)
    if not task or not can_view_task(task, current_user.id):
        return None, fail("Task not found.", 404)
    return task, None


def ensure_can_edit(cosmos: CosmosService, task_id: str):
    task = cosmos.get_task(task_id)
    if not task or not can_edit_task(task, current_user.id):
        return None, fail("Task not found.", 404)
    return task, None


def list_visible_tasks(cosmos: CosmosService, user_id: str, status=None, priority=None,
                       limit: int = 20, offset: int = 0, sort=None, order: str = "asc"):
    """
    Visible tasks = tasks where (owner_id == user_id OR assignee_id == user_id)
    Implemented directly against cosmos.tasks container so we don't have to change CosmosService.
    Returns (items, total)
    """
    where = ["(c.owner_id = @uid OR c.assignee_id = @uid)"]
    params = [{"name": "@uid", "value": user_id}]

    if status:
        where.append("c.status = @status")
        params.append({"name": "@status", "value": status})
    if priority:
        where.append("c.priority = @priority")
        params.append({"name": "@priority", "value": priority})

    where_sql = "WHERE " + " AND ".join(where)

    order_sql = ""
    if sort:
        direction = "DESC" if order == "desc" else "ASC"
        order_sql = f" ORDER BY c.{sort} {direction}"

    items_query = f"SELECT * FROM c {where_sql}{order_sql} OFFSET @offset LIMIT @limit"
    items_params = params + [{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}]

    count_query = f"SELECT VALUE COUNT(1) FROM c {where_sql}"

    items = list(cosmos.tasks.query_items(items_query, items_params, enable_cross_partition_query=True))
    total = list(cosmos.tasks.query_items(count_query, params, enable_cross_partition_query=True))[0]

    return items, int(total)


# -------------------------
# Home
# -------------------------

@bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("routes.ui_tasks"))
    return render_template("home.html")


# -------------------------
# Auth (UI)
# -------------------------

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("routes.ui_tasks"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(request.url)

        cosmos = CosmosService()
        if cosmos.get_user_by_email(email):
            flash("Email already registered.", "danger")
            return redirect(request.url)

        pw_hash = generate_password_hash(password)
        created = cosmos.create_user(email=email, password_hash=pw_hash)

        user = User.from_cosmos(created)
        login_user(user)
        flash("Account created. You're logged in.", "success")
        return redirect(url_for("routes.ui_tasks"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("routes.ui_tasks"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        cosmos = CosmosService()
        data = cosmos.get_user_by_email(email)

        if not data or not check_password_hash(data.get("password_hash", ""), password):
            flash("Invalid credentials.", "danger")
            return redirect(request.url)

        user = User.from_cosmos(data)
        login_user(user)
        flash("Logged in.", "success")
        return redirect(url_for("routes.ui_tasks"))

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("routes.login"))


# -------------------------
# API (login required + assignee visibility)
# -------------------------

@bp.route("/tasks", methods=["POST"])
@login_required
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
        "owner_id": current_user.id,
        "assignee_id": None,
    }

    try:
        cosmos = CosmosService()
        created = cosmos.create_task(task)
        return ok(serialize_task(created), message="Task created.", status=201)
    except Exception:
        current_app.logger.exception("Failed to create task")
        return fail("Internal server error.", 500)


@bp.route("/tasks", methods=["GET"])
@login_required
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
        items, total = list_visible_tasks(
            cosmos=cosmos,
            user_id=current_user.id,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order
        )
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
        "filters": {"status": status, "priority": priority},
        "sorting": {"sort": sort, "order": order}
    })


@bp.route("/tasks/<task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    try:
        cosmos = CosmosService()
        task, err = ensure_can_view(cosmos, task_id)
        if err:
            return err
        return ok(serialize_task(task))
    except Exception:
        current_app.logger.exception("Failed to get task")
        return fail("Internal server error.", 500)


@bp.route("/tasks/<task_id>", methods=["PATCH"])
@login_required
def update_task(task_id):
    auth_err = require_api_token()
    if auth_err:
        return auth_err

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    # Owner can update all of these. Assignee can update ONLY status.
    owner_allowed = {"title", "description", "status", "priority", "deadline"}
    assignee_allowed = {"status"}

    try:
        cosmos = CosmosService()
        task, err = ensure_can_view(cosmos, task_id)
        if err:
            return err

        if can_edit_task(task, current_user.id):
            allowed = owner_allowed
        else:
            allowed = assignee_allowed

        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return fail("No valid fields provided for update.", 400)

        if "status" in updates and updates["status"] not in ALLOWED_STATUSES:
            return fail(f"Invalid status. Allowed: {sorted(ALLOWED_STATUSES)}", 400)
        if "priority" in updates and updates["priority"] not in ALLOWED_PRIORITIES:
            return fail(f"Invalid priority. Allowed: {sorted(ALLOWED_PRIORITIES)}", 400)

        updated = cosmos.update_task(task_id, updates)
        return ok(serialize_task(updated), message="Task updated.")
    except Exception:
        current_app.logger.exception("Failed to update task")
        return fail("Internal server error.", 500)


@bp.route("/tasks/<task_id>/upload", methods=["POST"])
@login_required
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
        cosmos = CosmosService()
        task, err = ensure_can_view(cosmos, task_id)
        if err:
            return err

        blob = BlobService()
        file_url = blob.upload_file(f, filename)

        updated = cosmos.update_task(task_id, {"file_url": file_url})
        return ok(serialize_task(updated), message="File uploaded.")
    except Exception:
        current_app.logger.exception("Failed to upload file")
        return fail("Internal server error.", 500)


# -------------------------
# UI (login required + assignee visibility)
# -------------------------

@bp.route("/ui/tasks", methods=["GET"])
@login_required
def ui_tasks():
    status, priority, _ = validate_filters(request.args)
    limit, offset, _ = parse_pagination(request.args)
    sort, order, _ = validate_sorting(request.args)

    cosmos = CosmosService()
    try:
        items, total = list_visible_tasks(
            cosmos=cosmos,
            user_id=current_user.id,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order
        )
    except Exception:
        current_app.logger.exception("UI list failed")
        items, total = [], 0

    tasks = [serialize_task(i) for i in items]
    pagination = {"limit": limit, "offset": offset, "total": total, "has_more": (offset + limit) < total}
    filters = {"status": status, "priority": priority}
    sorting = {"sort": sort, "order": order}

    return render_template("tasks.html", tasks=tasks, pagination=pagination, filters=filters, sorting=sorting)


@bp.route("/ui/tasks/new", methods=["GET", "POST"])
@login_required
def ui_new_task():
    if request.method == "POST":
        data = request.form.to_dict()

        title = (data.get("title") or "").strip()
        if not title:
            flash("Title is required.", "danger")
            return redirect(request.url)

        status = data.get("status", "todo")
        priority = data.get("priority", "medium")

        if status not in ALLOWED_STATUSES:
            flash("Invalid status.", "danger")
            return redirect(request.url)
        if priority not in ALLOWED_PRIORITIES:
            flash("Invalid priority.", "danger")
            return redirect(request.url)

        cosmos = CosmosService()
        cosmos.create_task({
            "title": title,
            "description": (data.get("description") or "").strip(),
            "status": status,
            "priority": priority,
            "deadline": data.get("deadline"),
            "file_url": None,
            "owner_id": current_user.id,
            "assignee_id": None,
        })

        flash("Task created.", "success")
        return redirect(url_for("routes.ui_tasks"))

    return render_template("new_task.html")


@bp.route("/ui/tasks/<task_id>/status/<status>", methods=["POST"])
@login_required
def ui_set_status(task_id, status):
    if status not in ALLOWED_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    cosmos = CosmosService()
    task, err = ensure_can_view(cosmos, task_id)
    if err:
        flash("Task not found.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    cosmos.update_task(task_id, {"status": status})
    flash("Status updated.", "success")
    return redirect(url_for("routes.ui_tasks"))


@bp.route("/ui/tasks/<task_id>/upload", methods=["GET", "POST"])
@login_required
def ui_upload(task_id):
    cosmos = CosmosService()
    task, err = ensure_can_view(cosmos, task_id)
    if err:
        flash("Task not found.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    if request.method == "POST":
        if "file" not in request.files:
            flash("No file provided.", "danger")
            return redirect(request.url)

        f = request.files["file"]
        if not f.filename:
            flash("Empty filename.", "danger")
            return redirect(request.url)

        filename = secure_filename(f.filename)

        blob = BlobService()
        url = blob.upload_file(f, filename)

        cosmos.update_task(task_id, {"file_url": url})
        flash("File uploaded.", "success")
        return redirect(url_for("routes.ui_tasks"))

    return render_template("upload.html", task_id=task_id)


@bp.route("/ui/tasks/<task_id>/edit", methods=["GET", "POST"])
@login_required
def ui_edit_task(task_id):
    cosmos = CosmosService()
    task, err = ensure_can_edit(cosmos, task_id)
    if err:
        flash("Task not found.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    if request.method == "POST":
        data = request.form.to_dict()

        title = (data.get("title") or "").strip()
        if not title:
            flash("Title is required.", "danger")
            return redirect(request.url)

        status = data.get("status", task.get("status"))
        priority = data.get("priority", task.get("priority"))

        if status not in ALLOWED_STATUSES:
            flash("Invalid status.", "danger")
            return redirect(request.url)
        if priority not in ALLOWED_PRIORITIES:
            flash("Invalid priority.", "danger")
            return redirect(request.url)

        updates = {
            "title": title,
            "description": (data.get("description") or "").strip(),
            "status": status,
            "priority": priority,
            "deadline": data.get("deadline"),
        }

        cosmos.update_task(task_id, updates)
        flash("Task updated.", "success")
        return redirect(url_for("routes.ui_tasks"))

    view_task = {
        "title": task.get("title", ""),
        "description": task.get("description", ""),
        "status": task.get("status", "todo"),
        "priority": task.get("priority", "medium"),
        "deadline": task.get("deadline", ""),
    }
    return render_template("edit_task.html", task=view_task)


@bp.route("/ui/tasks/<task_id>/delete", methods=["POST"])
@login_required
def ui_delete_task(task_id):
    cosmos = CosmosService()
    task, err = ensure_can_edit(cosmos, task_id)
    if err:
        flash("Task not found.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    cosmos.delete_task(task_id)
    flash("Task deleted.", "success")
    return redirect(url_for("routes.ui_tasks"))


@bp.route("/ui/tasks/<task_id>/assign", methods=["GET", "POST"])
@login_required
def ui_assign(task_id):
    cosmos = CosmosService()
    task, err = ensure_can_edit(cosmos, task_id)
    if err:
        flash("Task not found.", "danger")
        return redirect(url_for("routes.ui_tasks"))

    if request.method == "POST":
        assignee_id = (request.form.get("assignee_id") or "").strip()
        if not assignee_id:
            flash("Assignee ID is required.", "danger")
            return redirect(request.url)

        assignee = cosmos.get_user_by_id(assignee_id)
        if not assignee:
            flash("User not found (invalid ID).", "danger")
            return redirect(request.url)

        cosmos.update_task(task_id, {"assignee_id": assignee_id})
        flash("Task assigned.", "success")

        # Send email (if configured)
        email_service = EmailService()
        if email_service.is_configured():
            subject = f"You were assigned a task: {task.get('title','(no title)')}"
            body = (
                f"Hi!\n\n"
                f"You have been assigned a task.\n\n"
                f"Title: {task.get('title','')}\n"
                f"Description: {task.get('description','')}\n"
                f"Priority: {task.get('priority','')}\n"
                f"Status: {task.get('status','')}\n"
                f"Deadline: {task.get('deadline','')}\n\n"
                f"Task ID: {task.get('id')}\n"
            )
            try:
                email_service.send(assignee["email"], subject, body)
                flash("Email sent to assignee.", "info")
            except Exception:
                current_app.logger.exception("Failed to send assignment email")
                flash("Assigned, but email failed to send (check logs).", "warning")
        else:
            flash("Assigned (email not configured).", "warning")

        return redirect(url_for("routes.ui_tasks"))

    return render_template("assign.html", task_id=task_id)
