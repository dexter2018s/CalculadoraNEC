from abc import ABC, abstractmethod
from typing import List, Tuple
from .components import Load, CircuitBreaker, Cable

class DistributionBoardCalculator(ABC):
    
    @abstractmethod
    def select_breaker(self, load: Load) -> Tuple[CircuitBreaker, str]:
        """Selects an appropriate circuit breaker for the given load. Returns (Breaker, Standard Ref)."""
        pass

    @abstractmethod
    def select_cable(self, load: Load, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        """Selects an appropriate cable for the given load and breaker. Returns (Cable, Standard Ref)."""
        pass

    @abstractmethod
    def calculate_feeder_conductors(self, loads: List[Load], user_demand_factor: float = 1.0) -> Tuple[float, Cable, str]:
        """Calculates feeder conductors based on total load. Returns (Total Amps, Cable, Standard Ref)."""
        pass

    @abstractmethod
    def calculate_main_protection(self, loads: List[Load], feeder_cable: Cable) -> Tuple[CircuitBreaker, str]:
        """Selects main protection based on loads and feeder cable. Returns (Breaker, Standard Ref)."""
        pass

    @abstractmethod
    def calculate_grounding_conductor(self, phase_cable: Cable, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        """Calculates grounding/PE conductor. Returns (Cable, Standard Ref)."""
        pass

    def calculate_circuit(self, load: Load) -> Tuple[CircuitBreaker, Cable, str]:
        """Performs the full calculation for a circuit. Returns (Breaker, Cable, Standard Ref)."""
        breaker, breaker_ref = self.select_breaker(load)
        cable, cable_ref = self.select_cable(load, breaker)
        combined_ref = f"Breaker: {breaker_ref} | Cable: {cable_ref}"
        return breaker, cable, combined_ref
