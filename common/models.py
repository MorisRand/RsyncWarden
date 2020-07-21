from typing import Optional, List, Tuple
from enum import Enum, auto
from pydantic import BaseModel


class Status(Enum):
    IntegrityFailed = auto()
    Done = auto()

class ClientMessage(BaseModel):
    run: str
    status: Status
    failed_files: Optional[List[Tuple[str, str]]] = None
