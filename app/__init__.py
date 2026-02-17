from flask import Flask, request
from dotenv import load_dotenv
from flask_login import LoginManager

from app.routes import bp
from app.utils.api import fail
from app.services.cosmos_service import CosmosService
from app.auth_models import User

def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object("config.Config")

    login_manager = LoginManager()
    login_manager.login_view = "routes.login"  # endpoint name
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        cosmos = CosmosService()
        data = cosmos.get_user_by_id(user_id)
        return User.from_cosmos(data) if data else None

    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_):
        return fail("Not found.", 404)

    @app.errorhandler(500)
    def server_error(_):
        if request.path.startswith("/ui/") or request.path in ("/login", "/register"):
            return "<h1>500 - Internal Server Error</h1><p>Check Log Stream.</p>", 500
        return fail("Internal server error.", 500)

    return app
