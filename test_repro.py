from core.models import LoadInput, InstallationParams, ConduitType, ConductorMaterial, InsulationRating
from standards.nec_logic import NECLogic

def test_user_case():
    print("--- Reproducing User Scenario ---")
    
    # User inputs
    power = 30000 # 30 KW
    voltage = 400
    phases = 3
    pf = 0.85
    is_continuous = True
    temp_c = 64
    conduit = ConduitType.STEEL
    grouping = 6
    ins_rating = InsulationRating.TEMP_75
    length = 1.0 # meters
    
    load = LoadInput(
        name="carga",
        power_watts=power,
        voltage=voltage,
        phases=phases,
        is_continuous=is_continuous,
        is_motor=False,
        power_factor=pf,
        quantity=1
    )
    
    params = InstallationParams(
        length_meters=length,
        conduit_type=conduit,
        ambient_temp_c=temp_c,
        raceway_count=grouping,
        conductor_material=ConductorMaterial.COPPER,
        insulation_rating=ins_rating
    )
    
    print(f"Load: {power/1000}kW, {voltage}V, {phases}Ph, PF {pf}")
    print(f"Env: {temp_c}C, Grouping {grouping}, Steel Conduit")
    
    # Calculate
    res = NECLogic.select_conductor_and_breaker(load, params)
    
    print("\n--- Result ---")
    print(f"Size: {res.size}")
    print(f"Ampacity: {res.ampacity}")
    print(f"Breaker: {res.breaker_rating}")
    print(f"VD%: {res.voltage_drop_percent:.4f}%")
    print(f"Notes: {res.reference_notes}")
    
    # Calculate Feeder for Fun
    feeder = NECLogic.calculate_main_feeder([load])
    print("\n--- Feeder ---")
    print(feeder)

if __name__ == "__main__":
    test_user_case()
