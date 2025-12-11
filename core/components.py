from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Standard(Enum):
    IEC = "IEC"
    NEMA = "NEMA"

@dataclass
class Load:
    name: str
    power_kw: float  # Power in kW
    voltage: float
    phases: int  # 1 or 3
    power_factor: float = 0.9
    is_continuous: bool = False  # Relevant for NEC/NEMA (Lighting, heating)
    is_motor: bool = False       # Relevant for NEC 430 / IEC Motor handling
    demand_factor: float = 1.0   # User defined demand factor (0.0 to 1.0)

    @property
    def current_amps(self) -> float:
        if self.phases == 1:
            return (self.power_kw * 1000) / (self.voltage * self.power_factor)
        elif self.phases == 3:
            return (self.power_kw * 1000) / (self.voltage * 1.732 * self.power_factor)
        return 0.0

@dataclass
class CircuitBreaker:
    rated_current: float
    poles: int
    breaking_capacity_ka: float = 10.0
    model: str = "Generic"

@dataclass
class Cable:
    size_mm2: Optional[float] = None  # For IEC
    size_awg: Optional[str] = None    # For NEMA
    ampacity: float = 0.0
    insulation: str = "PVC"
