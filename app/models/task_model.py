from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str
    priority: str
    deadline: str  # ISO string
    file_url: Optional[str] = None
