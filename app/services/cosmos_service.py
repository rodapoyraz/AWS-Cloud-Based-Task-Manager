import os
import uuid
from azure.cosmos import CosmosClient, PartitionKey

class CosmosService:
    def __init__(self):
        self.client = CosmosClient(
            os.getenv("COSMOS_ENDPOINT"),
            credential=os.getenv("COSMOS_KEY")
        )

        self.database = self.client.create_database_if_not_exists(
            id=os.getenv("COSMOS_DB_NAME")
        )

        self.container = self.database.create_container_if_not_exists(
            id=os.getenv("COSMOS_CONTAINER_NAME"),
            partition_key=PartitionKey(path=os.getenv("COSMOS_PARTITION_KEY", "/id")),
            offer_throughput=400
        )

    def create_task(self, task_data: dict) -> dict:
        task_data["id"] = str(uuid.uuid4())
        return self.container.create_item(task_data)

    def list_tasks(self) -> list:
        return list(self.container.read_all_items())

    def get_task(self, task_id: str) -> dict:
        return self.container.read_item(item=task_id, partition_key=task_id)

    def update_task(self, task_id: str, updated_data: dict) -> dict:
        item = self.get_task(task_id)
        item.update(updated_data)
        return self.container.replace_item(item=task_id, body=item)

    def delete_task(self, task_id: str) -> None:
        self.container.delete_item(item=task_id, partition_key=task_id)
