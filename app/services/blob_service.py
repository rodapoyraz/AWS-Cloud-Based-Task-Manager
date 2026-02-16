import os
import uuid
from azure.storage.blob import BlobServiceClient

class BlobService:
    def __init__(self):
        self.client = BlobServiceClient.from_connection_string(
            os.getenv("BLOB_CONNECTION_STRING")
        )
        self.container = self.client.get_container_client(
            os.getenv("BLOB_CONTAINER_NAME", "taskfiles")
        )

    def upload_file(self, file) -> str:
        filename = f"{uuid.uuid4()}_{file.filename}"
        blob_client = self.container.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        return blob_client.url
