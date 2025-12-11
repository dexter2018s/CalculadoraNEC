import math
from typing import Tuple, List
from core.calculator import DistributionBoardCalculator
from core.components import Load, CircuitBreaker, Cable

class IECCalculator(DistributionBoardCalculator):
    # Standard IEC breaker ratings (Amps)
    BREAKER_RATINGS = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 250, 400, 630]

    # Simplified PVC Copper Cable Ampacity (Approximate values for single core in conduit)
    # Size (mm2) -> Amps
    CABLE_AMPACITY = {
        1.5: 17.5,
        2.5: 24,
        4: 32,
        6: 41,
        10: 57,
        16: 76,
        25: 101,
        35: 125,
        50: 151,
        70: 192,
        95: 232,
        120: 269,
        150: 309
    }

    def select_breaker(self, load: Load) -> Tuple[CircuitBreaker, str]:
        ib = load.current_amps
        # Select first rating >= Ib
        for rating in self.BREAKER_RATINGS:
            if rating >= ib:
                return CircuitBreaker(rated_current=rating, poles=load.phases), "IEC 60898 Standard Rating"
        
        # If exceeds max standard list, return largest (simplified)
        return CircuitBreaker(rated_current=self.BREAKER_RATINGS[-1], poles=load.phases), "IEC 60898 (Max)"

    def select_cable(self, load: Load, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        in_rating = breaker.rated_current
        # Select cable where Iz >= In
        for size, ampacity in self.CABLE_AMPACITY.items():
            if ampacity >= in_rating:
                return Cable(size_mm2=size, ampacity=ampacity, insulation="PVC"), "IEC 60364-5-52 Simplified"
        
        return Cable(size_mm2=150, ampacity=309, insulation="PVC"), "IEC 60364-5-52 (Max)"

    def calculate_feeder_conductors(self, loads: List[Load], user_demand_factor: float = 1.0) -> Tuple[float, Cable, str]:
        # IEC 61439-1 Table 101 - Diversity Factors / Rated Diversity Factor (RDF)
        # 2-3 circuits: 0.9
        # 4-5 circuits: 0.8
        # 6-9 circuits: 0.7
        # 10+ circuits: 0.6
        num_circuits = len(loads)
        if num_circuits <= 1:
            rdf = 1.0
        elif num_circuits <= 3:
            rdf = 0.9
        elif num_circuits <= 5:
            rdf = 0.8
        elif num_circuits <= 9:
            rdf = 0.7
        else:
            rdf = 0.6
        
        # Apply user demand factor override if present and stricter?
        # Or just multiply? Let's treat user_demand_factor as an additional factor or override.
        # Requestion implies "Excepcion NEC 430.26" which is user defined. 
        # For IEC, let's allow it to override RDF if provided != 1.0.
        
        if user_demand_factor < 1.0:
            rdf = user_demand_factor
            rdf_ref = f"User Demand Factor ({rdf*100}%)"
        else:
            rdf_ref = f"IEC 61439-1 Table 101 (RDF={rdf})"

        # Calculate standard "Design Current" (Ib) sum
        sum_ib = sum(l.current_amps for l in loads)
        
        # Apply RDF
        total_current_design = sum_ib * rdf
        ref = f"{rdf_ref} & IEC 60364-5-52"

        # Select cable for the total current
        # Using simplified table again for now (max 309A)
        # Ideally should have parallel calc here too but keeping simple for now
        selected_cable, cable_ref = self._select_cable_for_amps(total_current_design)
        
        actual_ref = f"{ref} | {cable_ref}"
        return total_current_design, selected_cable, actual_ref

    def _select_cable_for_amps(self, amps: float) -> Tuple[Cable, str]:
        for size, ampacity in self.CABLE_AMPACITY.items():
            if ampacity >= amps:
                return Cable(size_mm2=size, ampacity=ampacity, insulation="PVC"), "IEC 60364-5-52"
        return Cable(size_mm2=150, ampacity=309, insulation="PVC"), "IEC 60364-5-52 (Max - Needs Parallel)"

    def calculate_main_protection(self, loads: List[Load], feeder_cable: Cable) -> Tuple[CircuitBreaker, str]:
        # Main breaker should protect the feeder cable (In <= Iz)
        # And should be > Total Design Current (In > Ib)
        # Logic: Find breaker where Ib_total <= In <= Iz_cable
        
        # Recalculate Ib_total just to be sure or pass it in. 
        # For this design, we trust the feeder cable selection was based on Ib_total
        # So essentially In <= Iz_cable.
        
        limit_amps = feeder_cable.ampacity
        selected_breaker = None
        
        # Iterate backwards to find largest breaker <= limit_amps
        # BUT wait, normally Main Breaker is sized to Load, then Cable sized to Breaker.
        # Here we sized cable to Load*RDF. 
        # So Breaker nominal current should be closest standard above Load*RDF, 
        # AND Cable must be >= Breaker.
        
        # Let's adjust approach: 
        # In this method we just pick a breaker that fits the cable capacity for protection
        # assuming the cable is already sized for the load.
        
        for rating in reversed(self.BREAKER_RATINGS):
            if rating <= limit_amps:
                selected_breaker = CircuitBreaker(rated_current=rating, poles=3) # Assuming 3P main
                break
        
        if not selected_breaker:
             selected_breaker = CircuitBreaker(rated_current=self.BREAKER_RATINGS[0], poles=3)

        return selected_breaker, f"IEC 60364-4-43 (In <= Iz={limit_amps}A)"

    def calculate_grounding_conductor(self, phase_cable: Cable, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        # IEC 60364-5-54 Table 54.2
        # S <= 16  -> S_pe = S
        # 16 < S <= 35 -> S_pe = 16
        # S > 35   -> S_pe = S / 2
        
        s_phase = phase_cable.size_mm2
        if s_phase is None:
             return Cable(size_mm2=0, ampacity=0, insulation="PE"), "Error: No Phase Size"
             
        if s_phase <= 16:
            s_pe = s_phase
        elif s_phase <= 35:
            s_pe = 16
        else:
            s_pe = s_phase / 2
            
        return Cable(size_mm2=s_pe, ampacity=0, insulation="G/Y"), "IEC 60364-5-54 Table 54.2"
