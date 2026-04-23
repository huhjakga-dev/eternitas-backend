from pydantic import BaseModel, model_validator
from typing import Optional, Annotated
from annotated_types import Ge, Le
from src.common.schema import CargoGrade, CrewType, DamageType, EquipmentType

Stat      = Annotated[int, Ge(1), Le(10)]
CargoStat = Annotated[int, Ge(10), Le(50)]


class CreateCrewRunner(BaseModel):
    crew_name:        str
    crew_type:        CrewType = CrewType.VOLUNTEER
    health:           Stat = 1
    mentality:        Stat = 1
    strength:         Stat = 1
    inteligence:      Stat = 1
    luckiness:        Stat = 1
    mechanization_lv: int  = 0

    @model_validator(mode="after")
    def check_stat_sum(self) -> "CreateCrewRunner":
        total = self.health + self.mentality + self.strength + self.inteligence + self.luckiness
        if total > 25:
            raise ValueError(f"스탯 합계 25 초과 (현재: {total})")
        return self


class CreateCargoRunner(BaseModel):
    cargo_name:  str
    cargo_code:  Optional[str]  = None
    grade:       CargoGrade
    damage_type: DamageType     = DamageType.HP
    health:      CargoStat      = 10
    mentality:   CargoStat      = 10
    strength:    CargoStat      = 10
    inteligence: CargoStat      = 10
    cause:       CargoStat      = 10


class StatModifier(BaseModel):
    health:      float = 0.0
    mentality:   float = 0.0
    strength:    float = 0.0
    inteligence: float = 0.0
    luckiness:   float = 0.0


class EquipmentEffects(StatModifier):
    """StatModifier + 전투 스탯 (무기 전용)"""
    hit_bonus:  int = 0       # 명중 보정값 (luck 굴림에 더함)
    damage_min: int = 0       # 명중 시 최소 데미지
    damage_max: int = 0       # 명중 시 최대 데미지
    min_roll:   int = 0       # 0 초과 시: 굴림값의 하한선 (ex. 15 고정)


class CreateEquipment(BaseModel):
    name:           str
    equipment_type: EquipmentType
    description:    Optional[str]    = None
    effects:        EquipmentEffects = EquipmentEffects()
    is_default:     bool             = False


class CreateStatusEffect(BaseModel):
    name:        str
    description: Optional[str] = None
    stat_json:   StatModifier  = StatModifier()


class HpSpDelta(BaseModel):
    hp_delta: int = 0
    sp_delta: int = 0
    note:     Optional[str] = None


class CreateCargoPattern(BaseModel):
    cargo_id:               str
    pattern_name:           str
    description:            Optional[str]   = None
    answer:                 Optional[str]   = None
    buff_stat_json:         StatModifier    = StatModifier()
    buff_damage_reduction:  float           = 0.0
    debuff_stat_json:       StatModifier    = StatModifier()
    debuff_demage_increase: float           = 0.0
    instant_kill:           bool            = False
