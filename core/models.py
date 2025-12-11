from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ConduitType(Enum):
    PVC = "PVC"
    STEEL = "Steel"
    ALUMINUM = "Aluminum"

class ConductorMaterial(Enum):
    COPPER = "Copper"
    ALUMINUM = "Aluminum"

class InsulationRating(Enum):
    TEMP_60 = 60
    TEMP_75 = 75
    TEMP_90 = 90

@dataclass
class LoadInput:
    name: str
    power_watts: float
    voltage: float
    phases: int  # 1 or 3
    is_continuous: bool = False
    is_motor: bool = False
    power_factor: float = 0.9
    quantity: int = 1
    override_amps: Optional[float] = None

@dataclass
class InstallationParams:
    length_meters: float
    conduit_type: ConduitType
    conductor_material: ConductorMaterial = ConductorMaterial.COPPER
    insulation_rating: InsulationRating = InsulationRating.TEMP_75
    ambient_temp_c: float = 30.0
    raceway_count: int = 3

@dataclass
class CableResult:
    size: str
    ampacity: float
    voltage_drop_percent: float
    parallel_runs: int = 1
    breaker_rating: float = 0.0
    reference_notes: str = ""
