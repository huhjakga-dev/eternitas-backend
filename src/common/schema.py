from enum import Enum


class CrewType(str, Enum):
    """
    승무원 타입 (자원, 사형수)
    """
    VOLUNTEER = "volunteer"
    CONVICT   = "convict"


class CargoGrade(str, Enum):
    """
    화물 등급
    규격, 비규격, 과적, 고착
    """
    STANDARD     = "standard"
    NON_STANDARD = "non_standard"
    OVERLOAD     = "overload"
    FIXED        = "fixed"


class WorkStatus(str, Enum):
    """
    작업 상태

    전조 대기, 전조 활성화, 메인 작업 준비(전조 완료), 완료
    """
    WAITING_PRECURSOR = "waiting_precursor"
    MAIN_WORK_READY   = "main_work_ready"
    RESOLVED          = "resolved"


class DamageType(str, Enum):
    """
    화물 데미지 타입
    체력/정신력/둘다
    """
    HP   = "hp"
    SP   = "sp"
    BOTH = "both"


class EquipmentType(str, Enum):
    WEAPON = "weapon"
    ARMOR  = "armor"


class PrecursorResult(str, Enum):
    """
    전조 판정 결과
    성공(정답), 무효(아무효과X), 실패, 대실패
    """
    SUCCESS       = "success"
    INVALID       = "invalid"
    FAIL          = "fail"
    CRITICAL_FAIL = "critical_fail"


class ReIsolationStatus(str, Enum):
    ACTIVE   = "active"
    RESOLVED = "resolved"
