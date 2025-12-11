from typing import Tuple, List, Optional
from core.calculator import DistributionBoardCalculator
from core.components import Load, CircuitBreaker, Cable

class NECCalculator(DistributionBoardCalculator):
    # Standard NEC breaker ratings (Amps) - NEC 240.6(A)
    BREAKER_RATINGS = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200, 225, 250, 300, 350, 400, 500, 600, 800, 1000, 1200]

    # NEC Table 310.16 for THHN/THWN-2 Copper (75 deg C column)
    # Size (AWG/kcmil) -> Amps
    CABLE_AMPACITY = {
        "14": 20, "12": 25, "10": 35, "8": 50, "6": 65, "4": 85,
        "3": 100, "2": 115, "1": 130, "1/0": 150, "2/0": 175,
        "3/0": 200, "4/0": 230, "250": 255, "300": 285, "350": 310,
        "400": 335, "500": 380, "600": 420
    }

    def select_breaker(self, load: Load) -> Tuple[CircuitBreaker, str]:
        ib = load.current_amps
        ref = "NEC 240.6(A)"
        required_rating = ib

        if load.is_motor:
            # NEC 430.52: Inverse Time Breaker up to 250% of FLA
            # We will select the first standard rating >= 150% FLA to ensure startup, 
            # but max 250%.
            min_target = ib * 1.50
            max_allowed = ib * 2.50
            ref = "NEC 430.52 (Motor 150-250%)"
            
            selected_rating = None
            for rating in self.BREAKER_RATINGS:
                if rating >= min_target:
                    selected_rating = rating
                    break
            
            # Check if selected exceeds max allowed
            if selected_rating and selected_rating > max_allowed:
                 # If next standard size is too big, technically we can't use it or need Exception.
                 # But usually we just take the one below if it handles start, or max.
                 # Let's simple cap at max allowed, but pick nearest standard down.
                 ref += " [CAPPED at 250%]"
                 # Find largest <= max_allowed
                 for rating in reversed(self.BREAKER_RATINGS):
                     if rating <= max_allowed:
                         selected_rating = rating
                         break
            
            if not selected_rating:
                 selected_rating = self.BREAKER_RATINGS[-1]

            return CircuitBreaker(rated_current=selected_rating, poles=load.phases), ref

        elif load.is_continuous:
            # NEC 210.19(A)(1) & 215.2(A)(1): 125% of continuous load
            required_rating = ib * 1.25
            ref += " & NEC 210.19(A)(1) (125% Continuous)"

        # Standard selection logic for non-motor
        for rating in self.BREAKER_RATINGS:
            if rating >= required_rating:
                return CircuitBreaker(rated_current=rating, poles=load.phases), ref
        
        return CircuitBreaker(rated_current=self.BREAKER_RATINGS[-1], poles=load.phases), ref + " (Max)"

    def select_cable(self, load: Load, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        ib = load.current_amps
        ref = "NEC 310.16 (75C)"
        min_ampacity = ib

        if load.is_motor:
            # NEC 430.22: Conductors >= 125% of Motor FLA
            min_ampacity = ib * 1.25
            ref = "NEC 430.22 (Motor 125%) & 310.16"
        elif load.is_continuous:
            # NEC 210.19(A)(1): Conductors >= 125% of Continuous Load
            min_ampacity = ib * 1.25
            ref += " & 210.19(A)(1)"
        
        # Also, conductor ampacity typically must closely match or exceed breaker for small loads,
        # unless it's a motor circuit where breaker >> cable is allowed.
        # For non-motor, cable must range breaker (NEC 240.4).
        if not load.is_motor:
             # Basic rule: Cable Ampacity >= Breaker Rating (simplified NEC 240.4)
             if breaker.rated_current > min_ampacity:
                 min_ampacity = breaker.rated_current
                 ref += " & NEC 240.4 (Cable >= Breaker)"

        selected_cable, cable_ref = self._select_cable_for_amps(min_ampacity)
        return selected_cable, f"{ref} | {cable_ref}"

    def calculate_feeder_conductors(self, loads: List[Load], user_demand_factor: float = 1.0) -> Tuple[float, Cable, str]:
        # NEC 430.24 (Motors) & NEC 215.2 (Feeders)
        # 1. Identify Largest Motor
        motors = [l for l in loads if l.is_motor]
        largest_motor = max(motors, key=lambda l: l.current_amps) if motors else None
        
        # 2. Sum of loads
        total_amps = 0.0
        ref_parts = []
        
        # Add 125% of Largest Motor
        if largest_motor:
            total_amps += largest_motor.current_amps * 0.25 # The extra 25%
            ref_parts.append("NEC 430.24 (25% Largest Motor)")
        
        # Sum all motors at 100% (Largest base 100% included here)
        sum_motors = sum(m.current_amps for m in motors)
        total_amps += sum_motors
        
        # Non-Motor Loads
        others = [l for l in loads if not l.is_motor]
        continuous_others = sum(l.current_amps for l in others if l.is_continuous)
        intermittent_others = sum(l.current_amps for l in others if not l.is_continuous)
        
        # NEC 215.2: 125% of Continuous + 100% of Non-Continuous
        total_amps += (continuous_others * 1.25)
        total_amps += intermittent_others
        
        if continuous_others > 0:
            ref_parts.append("NEC 215.2 (125% Continuous)")
            
        # Apply User Demand Factor (Exception NEC 430.26 / NEC 220.61(C) etc)
        # We apply this to the TOTAL calculated so far, though technically it might apply selectively.
        # For this tool, we assume global demand factor if provided < 1.0
        if user_demand_factor < 1.0:
            total_amps *= user_demand_factor
            ref_parts.append(f"NEC 430.26/220.87 (User DF={user_demand_factor*100}%)")

        ref = " + ".join(ref_parts) if ref_parts else "NEC Standard Load Sum"
        
        # Selection of Cable for Feeder
        # Check for Parallel Runs if Amps > Max Cable Capacity (420A for 600kcmil)
        # Or even earlier, e.g. > 400A usually better to parallel.
        
        selected_cable, cable_ref = self._select_cable_parallel_logic(total_amps)
        
        final_ref = f"{ref} | {cable_ref}"
        return total_amps, selected_cable, final_ref

    def _select_cable_parallel_logic(self, amps: float) -> Tuple[Cable, str]:
        # Try single run first
        if amps <= 420:
             return self._select_cable_for_amps(amps)
        
        # Parallel Runs Logic (NEC 310.10(H)) - Min 1/0 AWG
        # Try 2 sets, then 3 sets, etc.
        # We limit specific cables for parallel to avoid weird sizes. 
        # Good practices: 3/0, 250, 350, 500, 600 kcmil.
        candidate_sizes = ["1/0", "2/0", "3/0", "4/0", "250", "300", "350", "400", "500", "600"]
        
        num_sets = 2
        while num_sets <= 6: # Cap at 6 sets for sanity
            amps_per_set = amps / num_sets
            # Select cable for amps_per_set
            # Must be in candidate_sizes (>= 1/0)
            
            best_fit_cable = None
            best_fit_ampacity = 0
            
            for size in candidate_sizes:
                ampacity = self.CABLE_AMPACITY[size]
                if ampacity >= amps_per_set:
                    best_fit_cable = size
                    best_fit_ampacity = ampacity
                    break
            
            if best_fit_cable:
                # Found a viable parallel config
                cable_obj = Cable(size_awg=best_fit_cable, ampacity=best_fit_ampacity, insulation="THHN")
                # Hack: modify ampacity to reflect total system for main breaker check downstream
                cable_obj.ampacity = best_fit_ampacity * num_sets
                return cable_obj, f"NEC 310.10(H) ({num_sets}x {best_fit_cable} AWG/kcmil)"
            
            num_sets += 1
            
        # Fallback if massive
        return Cable(size_awg="CUSTOM", ampacity=amps, insulation="BUSBAR"), "Exceeds Standard Cable Capacity"

    def calculate_main_protection(self, loads: List[Load], feeder_cable: Cable) -> Tuple[CircuitBreaker, str]:
        # NEC 430.62(A) for Motor Feeder protection:
        # Rating <= Largest Branch Device + Sum of other loads
        # This is the MAX allowed.
        # But commonly we size close to Feeder Amps, just like a service entrance.
        
        # Simplified: Match Feeder Ampacity or slightly lower/higher standard.
        # NEC 240.4(B) allows next higher standard if <= 800A.
        # NEC 240.4(C) if > 800A, must not exceed.
        
        ampacity = feeder_cable.ampacity
        # Just pick first breaker >= ampacity? No, that exposes cable.
        # Pick breaker <= ampacity usually (unless 240.4(B) exception).
        
        selected_rating = None
        # Try to find standard rating directly below or equal
        for rating in reversed(self.BREAKER_RATINGS):
            if rating <= ampacity:
                selected_rating = rating
                break
        
        # Handle 240.4(B) Round Up rule if <= 800A
        if selected_rating and selected_rating < ampacity and ampacity <= 800:
            # Find next one up
            idx = self.BREAKER_RATINGS.index(selected_rating)
            if idx + 1 < len(self.BREAKER_RATINGS):
                 next_rating = self.BREAKER_RATINGS[idx+1]
                 # 240.4(B) condition: Next higher standard rating allowed if condcutors not part of branch circuit, etc.
                 # Generally allowed for feeders.
                 selected_rating = next_rating
                 return CircuitBreaker(rated_current=selected_rating, poles=3), f"NEC 240.4(B) (Round Up from Iz={ampacity}A)"
        
        if not selected_rating:
             selected_rating = self.BREAKER_RATINGS[0]
             
        return CircuitBreaker(rated_current=selected_rating, poles=3), f"NEC 240.4 (Strict In <= Iz={ampacity}A)"

    def calculate_grounding_conductor(self, phase_cable: Cable, breaker: CircuitBreaker) -> Tuple[Cable, str]:
        # NEC 250.122 Table - Based on Rating or Setting of Overcurrent Device
        rating = breaker.rated_current
        
        # Table 250.122
        table = [
            (15, "14"), (20, "12"), (60, "10"), (100, "8"),
            (200, "6"), (300, "4"), (400, "3"), (500, "2"),
            (600, "1"), (800, "1/0"), (1000, "2/0"), (1200, "3/0"),
            (1600, "4/0"), (2000, "250"), (2500, "350"), (3000, "400"),
            (4000, "500"), (5000, "700"), (6000, "800")
        ]
        
        selected_size = "800" # Max in table logic
        for limit, size in table:
            if rating <= limit:
                selected_size = size
                break
                
        return Cable(size_awg=selected_size, ampacity=0, insulation="Green"), "NEC 250.122 Table"

    def _select_cable_for_amps(self, amps: float) -> Tuple[Cable, str]:
        for size, ampacity in self.CABLE_AMPACITY.items():
            if ampacity >= amps:
                return Cable(size_awg=size, ampacity=ampacity, insulation="THHN"), "NEC 310.16"
        return Cable(size_awg="600", ampacity=420, insulation="THHN"), "NEC 310.16 (Max)"
