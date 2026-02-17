import os
import uuid

from azure.storage.blob import BlobServiceClient, ContentSettings


class BlobService:
    def __init__(self):
        conn_str = os.getenv("BLOB_CONNECTION_STRING")
        container_name = os.getenv("BLOB_CONTAINER_NAME", "taskfiles")

        if not conn_str:
            raise RuntimeError("Missing BLOB_CONNECTION_STRING environment variable.")

        self.client = BlobServiceClient.from_connection_string(conn_str)
        self.container = self.client.get_container_client(container_name)

        # Ensure container exists
        try:
            self.container.create_container()
        except Exception:
            # container probably already exists (or you lack permissions)
            pass

    def upload_file(self, file, filename: str = None) -> str:
        """
        file: Werkzeug FileStorage (request.files['file'])
        filename: sanitized filename (e.g., from secure_filename in routes)
        """
        original = filename or getattr(file, "filename", "upload.bin")
        blob_name = f"{uuid.uuid4()}_{original}"

        blob_client = self.container.get_blob_client(blob_name)

        content_type = getattr(file, "mimetype", None)
        content_settings = ContentSettings(content_type=content_type) if content_type else None

        # FileStorage is stream-like; upload its stream for reliability
        stream = getattr(file, "stream", file)

        blob_client.upload_blob(
            stream,
            overwrite=True,
            content_settings=content_settings
        )

        return blob_client.url
