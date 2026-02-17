import os
import uuid
from typing import Optional, Tuple, List, Dict

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError


class CosmosService:
    ALLOWED_SORT_FIELDS = {"title", "status", "priority", "deadline"}

    def __init__(self):
        endpoint = os.getenv("COSMOS_ENDPOINT")
        key = os.getenv("COSMOS_KEY")
        db_name = os.getenv("COSMOS_DB_NAME")

        tasks_container_name = os.getenv("COSMOS_CONTAINER_NAME")
        users_container_name = os.getenv("COSMOS_USERS_CONTAINER_NAME", "users")

        pk_path = os.getenv("COSMOS_PARTITION_KEY", "/id")  # keep /id

        if not endpoint or not key or not db_name or not tasks_container_name:
            raise RuntimeError("Missing Cosmos env vars (endpoint/key/db/container).")

        self.client = CosmosClient(endpoint, credential=key)
        self.database = self.client.create_database_if_not_exists(id=db_name)

        # Tasks container
        self.tasks = self.database.create_container_if_not_exists(
            id=tasks_container_name,
            partition_key=PartitionKey(path=pk_path),
            offer_throughput=400
        )

        # Users container
        self.users = self.database.create_container_if_not_exists(
            id=users_container_name,
            partition_key=PartitionKey(path="/id"),
            offer_throughput=400
        )

    # -------------------
    # Users
    # -------------------
    def create_user(self, email: str, password_hash: str, user_code: str) -> dict:
     user = {
        "id": str(uuid.uuid4()),
        "email": email.lower().strip(),
        "password_hash": password_hash,
        "user_code": user_code.strip().lower()
    }
     return self.users.create_item(user)


    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        try:
            return self.users.read_item(item=user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        q = "SELECT TOP 1 * FROM c WHERE c.email = @email"
        params = [{"name": "@email", "value": email.lower().strip()}]
        items = list(self.users.query_items(query=q, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

    # -------------------
    # Tasks (per-user)
    # -------------------
    def create_task(self, task_data: dict) -> dict:
        task_data = dict(task_data)
        task_data["id"] = str(uuid.uuid4())
        return self.tasks.create_item(task_data)

    def get_task(self, task_id: str) -> Optional[dict]:
        try:
            return self.tasks.read_item(item=task_id, partition_key=task_id)
        except CosmosResourceNotFoundError:
            return None

    def update_task(self, task_id: str, updated_data: dict) -> Optional[dict]:
        item = self.get_task(task_id)
        if not item:
            return None
        item.update(updated_data)
        return self.tasks.replace_item(item=task_id, body=item)

    def delete_task(self, task_id: str) -> bool:
        try:
            self.tasks.delete_item(item=task_id, partition_key=task_id)
            return True
        except CosmosResourceNotFoundError:
            return False


    def list_users(self) -> List[Dict]:
        query = "SELECT c.id, c.email FROM c"
        return list(self.users.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

    def list_tasks(
        self,
        owner_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: Optional[str] = None,
        order: str = "asc"
    ) -> Tuple[List[Dict], int]:
        where = ["c.owner_id = @owner_id"]
        params = [{"name": "@owner_id", "value": owner_id}]

        if status:
            where.append("c.status = @status")
            params.append({"name": "@status", "value": status})

        if priority:
            where.append("c.priority = @priority")
            params.append({"name": "@priority", "value": priority})

        where_sql = "WHERE " + " AND ".join(where)

        order_sql = ""
        if sort:
            if sort not in self.ALLOWED_SORT_FIELDS:
                raise ValueError(f"Invalid sort field: {sort}")
            direction = "DESC" if order == "desc" else "ASC"
            order_sql = f" ORDER BY c.{sort} {direction}"

        items_query = f"SELECT * FROM c {where_sql}{order_sql} OFFSET @offset LIMIT @limit"
        items_params = params + [{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}]

        count_query = f"SELECT VALUE COUNT(1) FROM c {where_sql}"

        items = list(self.tasks.query_items(items_query, items_params, enable_cross_partition_query=True))
        total = list(self.tasks.query_items(count_query, params, enable_cross_partition_query=True))[0]

        return items, int(total)

    def get_user_by_code(self, user_code: str) -> Optional[dict]:
        q = "SELECT TOP 1 * FROM c WHERE c.user_code = @code"
        params = [{"name": "@code", "value": user_code.strip().lower()}]
        items = list(self.users.query_items(query=q, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

    def list_users(self) -> List[Dict]:
        # show only friendly id + internal uuid
        query = "SELECT c.id, c.user_code FROM c"
        return list(self.users.query_items(query=query, enable_cross_partition_query=True))
