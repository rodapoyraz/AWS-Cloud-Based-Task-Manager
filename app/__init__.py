from flask import Flask
from dotenv import load_dotenv
from app.routes import bp

def create_app():
    load_dotenv()  # loads .env locally

    app = Flask(__name__)
    app.config.from_object("config.Config")  # loads config.py into app.config

    app.register_blueprint(bp)
    return app
