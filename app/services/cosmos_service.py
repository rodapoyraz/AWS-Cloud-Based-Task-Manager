import os
import uuid
from typing import Optional, Tuple, List, Dict

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError


class CosmosService:
    """
    Notes:
    - If your partition key is /id (default), listing tasks requires cross-partition queries.
    - Sorting works best if 'deadline' is stored as ISO date string: YYYY-MM-DD (lexicographically sortable).
    """

    ALLOWED_SORT_FIELDS = {"title", "status", "priority", "deadline"}

    def __init__(self):
        endpoint = os.getenv("COSMOS_ENDPOINT")
        key = os.getenv("COSMOS_KEY")
        db_name = os.getenv("COSMOS_DB_NAME")
        container_name = os.getenv("COSMOS_CONTAINER_NAME")
        pk_path = os.getenv("COSMOS_PARTITION_KEY", "/id")

        if not endpoint or not key or not db_name or not container_name:
            raise RuntimeError("Missing Cosmos DB environment variables (endpoint/key/db/container).")

        self.client = CosmosClient(endpoint, credential=key)

        self.database = self.client.create_database_if_not_exists(id=db_name)

        self.container = self.database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path=pk_path),
            offer_throughput=400
        )

    def create_task(self, task_data: dict) -> dict:
        task_data = dict(task_data)
        task_data["id"] = str(uuid.uuid4())
        return self.container.create_item(task_data)

    # Backward compatible helper (your previous routes fallback used get_all_tasks sometimes)
    def get_all_tasks(self) -> List[dict]:
        return list(self.container.read_all_items())

    # Keep an unfiltered "list all" for older code paths
    def list_tasks_all(self) -> List[dict]:
        return list(self.container.read_all_items())

    def get_task(self, task_id: str) -> Optional[dict]:
        try:
            return self.container.read_item(item=task_id, partition_key=task_id)
        except CosmosResourceNotFoundError:
            return None

    def update_task(self, task_id: str, updated_data: dict) -> Optional[dict]:
        item = self.get_task(task_id)
        if not item:
            return None
        item.update(updated_data)
        return self.container.replace_item(item=task_id, body=item)

    def delete_task(self, task_id: str) -> bool:
        try:
            self.container.delete_item(item=task_id, partition_key=task_id)
            return True
        except CosmosResourceNotFoundError:
            return False

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: Optional[str] = None,
        order: str = "asc"
    ) -> Tuple[List[Dict], int]:
        """
        Returns: (items, total)
        """

        where_clauses = []
        params = []

        if status:
            where_clauses.append("c.status = @status")
            params.append({"name": "@status", "value": status})

        if priority:
            where_clauses.append("c.priority = @priority")
            params.append({"name": "@priority", "value": priority})

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        order_sql = ""
        if sort:
            if sort not in self.ALLOWED_SORT_FIELDS:
                raise ValueError(f"Invalid sort field: {sort}")
            direction = "DESC" if order == "desc" else "ASC"
            # Cosmos requires ORDER BY c.<field>
            order_sql = f" ORDER BY c.{sort} {direction}"

        # Items query with pagination
        items_query = (
            f"SELECT * FROM c {where_sql}{order_sql} "
            "OFFSET @offset LIMIT @limit"
        )
        items_params = params + [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]

        # Total count query
        count_query = f"SELECT VALUE COUNT(1) FROM c {where_sql}"

        # Cross partition query is typically needed for listing
        items_iter = self.container.query_items(
            query=items_query,
            parameters=items_params,
            enable_cross_partition_query=True
        )
        items = list(items_iter)

        count_iter = self.container.query_items(
            query=count_query,
            parameters=params,
            enable_cross_partition_query=True
        )
        total = list(count_iter)[0] if count_iter else 0

        return items, int(total)
