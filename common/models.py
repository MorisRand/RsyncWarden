from enum import Enum, auto
from pydantic import BaseModel

class CopyStatus(Enum):
    ShouldCheckIntegrity = auto()
    CheckInProgress = auto()
    IntegrityFailed = auto()
    Done = auto()
