import math
from typing import Tuple, Optional

def convert_power_unit(val: float, unit: str, voltage: float, phases: int, pf: float) -> Tuple[float, Optional[float]]:
    """
    Converts input value to (Watts, Amps_Override).
    Returns (calculated_watts, override_amps)
    """
    unit = unit.strip().upper()
    
    # 1. Power Units
    if unit == "W": return (val, None)
    if unit == "kW": return (val * 1000.0, None) # Normalizing casing check
    if unit == "KW": return (val * 1000.0, None)
    if unit == "MW": return (val * 1000000.0, None)
    if unit == "HP": return (val * 746.0, None)
    
    # 2. Current Units
    if unit == "A":
        factor = math.sqrt(3) if phases == 3 else 1.0
        watts = val * voltage * factor * pf
        return (watts, val)
        
    # 3. Apparent/Reactive
    if unit in ["VA", "VAR"]: 
        return (val * pf, None)
    if unit in ["KVA", "KVAR"]:
        return (val * 1000.0 * pf, None)
    if unit in ["MVA", "MVAR"]:
        return (val * 1000000.0 * pf, None)
        
    # Default
    return (val, None)

def convert_length_unit(val: float, unit: str) -> float:
    """Returns length in meters."""
    unit = unit.strip().lower()
    if unit in ["m", "mts", "metros", "metro"]: return val
    if unit in ["ft", "pies", "pie"]: return val * 0.3048
    if unit in ["yd", "yarda", "yardas"]: return val * 0.9144
    return val
