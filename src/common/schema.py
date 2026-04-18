from enum import Enum


class CrewType(str, Enum):
    VOLUNTEER = "volunteer"
    CONVICT   = "convict"


class CargoGrade(str, Enum):
    STANDARD     = "standard"
    NON_STANDARD = "non_standard"
    OVERLOAD     = "overload"
    FIXED        = "fixed"


class WorkStatus(str, Enum):
    WAITING_PRECURSOR = "waiting_precursor"
    PRECURSOR_ACTIVE  = "precursor_active"
    MAIN_WORK_READY   = "main_work_ready"
    RESOLVED          = "resolved"


class PrecursorResult(str, Enum):
    SUCCESS       = "success"
    INVALID       = "invalid"       # 무효: 판정 자체가 성립 안 됨
    FAIL          = "fail"
    CRITICAL_FAIL = "critical_fail"
