import math
from typing import Tuple, Optional
from core.models import LoadInput, InstallationParams, CableResult, ConduitType, InsulationRating
from standards.nec_tables import NEC_310_16_COPPER, TABLE_9_IMPEDANCE, get_temp_correction, get_grouping_factor

BREAKER_RATINGS = [15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200, 225, 250, 300, 350, 400, 500, 600, 800, 1000, 1200]

class NECLogic:
    @staticmethod
    def calculate_design_current(load: LoadInput) -> float:
        # Use override if present (Already calculated Amps from Converter)
        if load.override_amps is not None:
             i_base = load.override_amps
        else:
             # Calculate from watts
             if load.phases == 1:
                i_base = load.power_watts / (load.voltage * load.power_factor)
             else:
                i_base = load.power_watts / (math.sqrt(3) * load.voltage * load.power_factor)
            
        # Continuous Load Rule
        factor = 1.25 if load.is_continuous else 1.0
        return i_base * factor

    @staticmethod
    def calculate_voltage_drop(
        current: float, 
        size_awg: str, 
        params: InstallationParams, 
        voltage: float, 
        phases: int,
        pf: float
    ) -> float:
        conduit = params.conduit_type
        # Map Aluminum conduit to PVC (non-magnetic) purely for X table lookup if needed
        lookup_conduit = ConduitType.PVC if conduit == ConduitType.ALUMINUM else conduit
        
        if size_awg not in TABLE_9_IMPEDANCE:
            return 999.0
            
        r_table, x_table = TABLE_9_IMPEDANCE[size_awg].get(lookup_conduit, (0.1, 0.1))
        
        theta = math.acos(pf)
        z_eff = (r_table * math.cos(theta)) + (x_table * math.sin(theta))
        
        length_ft = params.length_meters * 3.28084
        k = 1.732 if phases == 3 else 2.0
        
        vd_volts = (k * current * z_eff * length_ft) / 1000.0
        vd_percent = (vd_volts / voltage) * 100.0
        
        return vd_percent

    @staticmethod
    def select_conductor_and_breaker(load: LoadInput, params: InstallationParams) -> CableResult:
        i_req = NECLogic.calculate_design_current(load)
        
        # Derating Factors
        # Use user selected insulation rating for limit check?
        # Temperature Correction: NEC 310.15(B)(1)
        # Grouping Adjustment: NEC 310.15(C)(1)
        
        f_temp = get_temp_correction(params.ambient_temp_c, params.insulation_rating.value)
        f_group = get_grouping_factor(params.raceway_count)
        
        total_derating = f_temp * f_group
        
        selected_size = None
        selected_ampacity = 0.0
        final_vd = 0.0
        
        # Extended list of sizes
        sizes = ["14", "12", "10", "8", "6", "4", "3", "2", "1", "1/0", "2/0", "3/0", "4/0", 
                 "250", "300", "350", "400", "500", "600", "700", "750", "800", "900", "1000", "1250", "1500", "1750", "2000"]
        
        for size in sizes:
            if size not in NEC_310_16_COPPER: continue

            base_amps_check = NEC_310_16_COPPER[size][75] # Compliance with 75C terminals
            
            # Derated ampacity
            # Use the ampacity corresponding to the conductor's temp rating (75 or 90) as base for derating
            derating_base = NEC_310_16_COPPER[size][params.insulation_rating.value]
            derated_amps = derating_base * total_derating
            
            # CHECK 1: Load Capacity vs Terminal Rating (75C)
            if base_amps_check < i_req:
                continue
                
            # CHECK 2: Derated Ampacity vs Actual Continuous Load
            # load.override_amps is the "actual" current.
            # i_req is already 125% if continuous.
            # Comparing Derated (Nominal) vs Actual Load (100% Cont).
            # NEC 215.2(A)(1)(a) Exception: Derated ampacity must cover 100% of continuous load + non-cont.
            
            # Calculate actual load (Amps flowing)
            actual_load = i_req / 1.25 if load.is_continuous else i_req
            
            if derated_amps < actual_load:
                continue
                
            # CHECK 3: Voltage Drop
            # Using actual load current
            vd = NECLogic.calculate_voltage_drop(actual_load, size, params, load.voltage, load.phases, load.power_factor)
            
            if vd <= 3.0:
                selected_size = size
                # Capacity displayed is the lesser of derated or 75C? 
                # NEC says ampacity is the result of derating. 
                # But usable ampacity is limited by terminals.
                selected_ampacity = min(base_amps_check, derated_amps)
                final_vd = vd
                break
                
        if not selected_size:
            selected_size = "MAX_EXCEEDED"
            
        # Breaker Selection
        cable_capacity_for_breaker = NEC_310_16_COPPER[selected_size if selected_size != "MAX_EXCEEDED" else "600"][75]
        
        sel_breaker = 15
        for b in BREAKER_RATINGS:
            # Rule: Breaker >= Design Current
            if b >= i_req:
                sel_breaker = b
                break
                
        # User requested 75C vs 90C Output Label
        # If Insulation is 90C -> THHN/THWN-2
        # If Insulation is 75C -> THWN
        cable_type_str = "THHN/THWN-2 (90°C)" if params.insulation_rating.value == 90 else "THWN (75°C)"
        
        return CableResult(
            size=selected_size,
            ampacity=selected_ampacity,
            voltage_drop_percent=final_vd,
            breaker_rating=sel_breaker,
            reference_notes=f"Type: {cable_type_str} | Derating: {total_derating:.2f} (Temp {f_temp} * Grp {f_group})"
        )

    @staticmethod
    def calculate_main_feeder(loads: list[LoadInput], user_demand_factor: float = 1.0) -> dict:
        motors = [l for l in loads if l.is_motor]
        others = [l for l in loads if not l.is_motor]
        
        total_amps = 0.0
        max_motor_amps_unit = 0.0
        
        # Motors
        for m in motors:
            # Calculate UNIT current (for finding largest)
            if m.override_amps is not None:
                i_unit = m.override_amps
            else:
                 if m.phases == 1:
                    i_unit = m.power_watts / (m.voltage * m.power_factor)
                 else:
                    i_unit = m.power_watts / (math.sqrt(3) * m.voltage * m.power_factor)
            
            if i_unit > max_motor_amps_unit:
                max_motor_amps_unit = i_unit
            
            # Add to total (Quantity handled)
            total_amps += (i_unit * m.quantity)
            
        if max_motor_amps_unit > 0:
            total_amps += (max_motor_amps_unit * 0.25) # 25% of largest MOTOR UNIT
            
        # Others
        for l in others:
            if l.override_amps is not None:
                i_unit = l.override_amps
            else:
                 if l.phases == 1:
                    i_unit = l.power_watts / (l.voltage * l.power_factor)
                 else:
                    i_unit = l.power_watts / (math.sqrt(3) * l.voltage * l.power_factor)
            
            line_amps = i_unit * l.quantity
            
            if l.is_continuous:
                total_amps += (line_amps * 1.25)
            else:
                total_amps += line_amps
        
        # User Demand Factor
        if user_demand_factor < 1.0:
            total_amps *= user_demand_factor
            
        # Parallel Logic > 400A
        num_runs = 1
        selected_size = "TBD"
        
        sizes = ["1/0", "2/0", "3/0", "4/0", "250", "300", "350", "400", "500", "600", "750", "800", "1000", "1250", "1500", "1750", "2000"]
        
        if total_amps > 400:
            for n in range(1, 10): # Try up to 9 sets?
                current_per_set = total_amps / n
                found = False
                for s in sizes:
                    if s not in NEC_310_16_COPPER: continue
                    cap = NEC_310_16_COPPER[s][75]
                    if cap >= current_per_set:
                        selected_size = s
                        num_runs = n
                        found = True
                        break
                if found and num_runs > 1: break # Valid parallel
                if found and num_runs == 1 and current_per_set <= 420: break
        else:
             full_sizes = ["14", "12", "10", "8", "6", "4", "3", "2", "1"] + sizes
             for s in full_sizes:
                if NEC_310_16_COPPER.get(s, {}).get(75, 0) >= total_amps:
                    selected_size = s
                    break
        
        return {
            "total_amps": total_amps,
            "cable_size": selected_size,
            "parallel_runs": num_runs,
            "description": f"{num_runs}x {selected_size} AWG/kcmil per phase" if num_runs > 1 else f"{selected_size} AWG/kcmil"
        }
