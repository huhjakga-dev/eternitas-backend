from enum import Enum

class DamageType(str, Enum):
    HP = "hp"
    SP = "sp"
    BOTH = "both"

class WorkStatus(str, Enum):
    WAITING_PRECURSOR = "waiting_precursor"
    PRECURSOR_ACTIVE = "precursor_active"
    MAIN_WORK_READY = "main_work_ready"
    RESOLVED = "resolved"