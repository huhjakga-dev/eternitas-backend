from enum import Enum


class CrewType(str, Enum):
    VOLUNTEER = "volunteer"  # 자원 승무원
    CONVICT   = "convict"    # 사형수 승무원


class CargoGrade(str, Enum):
    STANDARD = "standard"
    NON_STANDARD = "non_standard"
    OVERLOAD = "overload"
    FIXED = "fixed"


class DamageType(str, Enum):
    HP = "hp"
    SP = "sp"
    BOTH = "both"


class WorkStatus(str, Enum):
    WAITING_PRECURSOR = "waiting_precursor"
    PRECURSOR_ACTIVE = "precursor_active"
    MAIN_WORK_READY = "main_work_ready"
    RESOLVED = "resolved"
