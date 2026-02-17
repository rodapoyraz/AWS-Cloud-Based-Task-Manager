from flask import Flask
from dotenv import load_dotenv

from app.routes import bp
from app.utils.api import fail


def create_app():
    load_dotenv()  # loads .env locally

    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Register routes
    app.register_blueprint(bp)

    # Error handlers (consistent JSON)
    @app.errorhandler(404)
    def not_found(_):
        return fail("Not found.", 404)

    @app.errorhandler(500)
    def server_error(_):
        return fail("Internal server error.", 500)

    return app
