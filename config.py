import os


class Config:
    # Cosmos
    COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
    COSMOS_KEY = os.getenv("COSMOS_KEY")
    COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
    COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")
    COSMOS_PARTITION_KEY = os.getenv("COSMOS_PARTITION_KEY", "/id")

    # Blob
    BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
    BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME", "taskfiles")

    # API Security (optional)
    API_TOKEN = os.getenv("API_TOKEN")  # if unset -> auth disabled (dev mode)

    # Flask basics
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Safer production defaults
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    TESTING = False
    PROPAGATE_EXCEPTIONS = False
    TRAP_HTTP_EXCEPTIONS = False
