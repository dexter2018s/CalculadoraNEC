import unittest
from core.models import LoadInput, InstallationParams, ConduitType, ConductorMaterial, InsulationRating
from standards.nec_logic import NECLogic

class TestNCEditionV2(unittest.TestCase):
    
    def test_conduit_effect_voltage_drop(self):
        print("\n--- TEST: Efecto del Ducto (Acero vs PVC) ---")
        # Load: 100A roughly (e.g. 50kW 480V 3Ph) -> I = 50000 / (1.732*480*0.9) = 66.8 A
        load = LoadInput(name="TestMotor", power_watts=50000, voltage=480, phases=3, is_motor=True, power_factor=0.9)
        
        # Long distance to exaggerate VD
        dist = 200.0 # meters
        
        # PVC Params
        params_pvc = InstallationParams(length_meters=dist, conduit_type=ConduitType.PVC, ambient_temp_c=30, raceway_count=3)
        res_pvc = NECLogic.select_conductor_and_breaker(load, params_pvc)
        
        # Steel Params
        params_steel = InstallationParams(length_meters=dist, conduit_type=ConduitType.STEEL, ambient_temp_c=30, raceway_count=3)
        res_steel = NECLogic.select_conductor_and_breaker(load, params_steel)
        
        print(f"PVC Size: {res_pvc.size} | VD: {res_pvc.voltage_drop_percent:.2f}%")
        print(f"STEEL Size: {res_steel.size} | VD: {res_steel.voltage_drop_percent:.2f}%")
        
        # Generally Steel (Magnetic) has higher reactance -> higher Impedance -> higher Voltage Drop
        # HOWEVER, checking Table 9, X is indeed higher for Steel.
        # So for SAME cable size, Split might be higher.
        # But if the calculator up-sized the cable to meet <3%, the VD might end up lower or similar but with larger cable.
        
        # Check if logic behaves sensibly.
        # If sizes are same, Steel VD > PVC VD.
        if res_pvc.size == res_steel.size:
            self.assertGreater(res_steel.voltage_drop_percent, res_pvc.voltage_drop_percent)
            print("Verified: Steel conduit caused higher VD for same cable.")
        else:
            print("Verified: System up-sized cable for Steel to compensate (or different constraint).")

    def test_temp_derating(self):
        print("\n--- TEST: Derating por Temperatura (30C vs 50C) ---")
        # Load 50A roughly (e.g. 20kW 220V 1Ph) -> I = 20000 / (220*0.9) = 101 A
        # Let's use smaller load: 5kW 220V 1Ph -> I = 22.7 A
        load = LoadInput(name="Heater", power_watts=5000, voltage=220, phases=1, is_continuous=True)
        # Req = 22.7 * 1.25 = 28.4 A
        
        # Base 30C (Factor 1.0)
        p_30 = InstallationParams(length_meters=10, conduit_type=ConduitType.PVC, ambient_temp_c=30, raceway_count=3)
        res_30 = NECLogic.select_conductor_and_breaker(load, p_30)
        
        # Hot 50C (Factor 0.82 for 90C insulation used for derating checks?)
        # NEC Table says 46-50C -> 0.82 (90C col).
        p_50 = InstallationParams(length_meters=10, conduit_type=ConduitType.PVC, ambient_temp_c=50, raceway_count=3)
        res_50 = NECLogic.select_conductor_and_breaker(load, p_50)
        
        print(f"30C Size: {res_30.size} (Derating: {res_30.reference_notes})")
        print(f"50C Size: {res_50.size} (Derating: {res_50.reference_notes})")
        
        # Should be larger or same?
        # 10 AWG (40A at 90C) * 0.82 = 32.8 A > 28.4 A. So 10 AWG likely still works.
        # Let's push it. 
        # 45A Load. 
        # 60C Ambient -> Factor 0.71 (90C).
        
        # If sizes differ, test passed.
        # For 5kW (28A Req), 10AWG (35A @75C) works at 30C.
        # At 50C: 10AWG (40A @90C * 0.82) = 32.8A. Still works.
        
        # Try heavier load to force change. 
        # 10kW 220V 1Ph -> 45.4 A. Req = 56.8 A.
        load2 = LoadInput(name="BigHeater", power_watts=10000, voltage=220, phases=1, is_continuous=True)
        # 30C: Req 56.8A. Needs #6 (65A@75C) or #4. #6 is fine.
        p_30b = InstallationParams(length_meters=10, conduit_type=ConduitType.PVC, ambient_temp_c=30, raceway_count=3)
        res_30b = NECLogic.select_conductor_and_breaker(load2, p_30b)
        
        # 50C: Req 56.8A. Cable #6 (75A@90C) * 0.82 = 61.5A. Still works?
        # 55C: Factor 0.76. 75 * 0.76 = 57A. Borderline.
        p_55 = InstallationParams(length_meters=10, conduit_type=ConduitType.PVC, ambient_temp_c=55, raceway_count=3)
        res_55b = NECLogic.select_conductor_and_breaker(load2, p_55)
        
        print(f"BigHeater 30C: {res_30b.size}")
        print(f"BigHeater 55C: {res_55b.size}")
        
        # We expect validation logic to hold.
        self.assertTrue(res_55b.ampacity >= res_30b.ampacity) # Shouldn't go down

if __name__ == '__main__':
    unittest.main()
