import unittest
from core.components import Load
from standards.nec import NECCalculator

class TestFactoryScenario(unittest.TestCase):
    def test_the_factory(self):
        print("\n--- TEST: THE FACTORY ---")
        calc = NECCalculator()
        loads = []
        
        # 1. Major Load: 80kW Motor, 480V 3Ph (Industrial Standard USA)
        # Power = 80kW. 
        # I = 80000 / (480 * 1.732 * 0.9) = 106.9 A
        large_motor = Load(name="Big Press", power_kw=80, voltage=480, phases=3, power_factor=0.9, is_motor=True)
        loads.append(large_motor)
        
        # 2. 20 Small Machines: 10kW, 480V 3Ph.
        # I = 10000 / (480 * 1.732 * 0.9) = 13.36 A each
        for i in range(20):
            loads.append(Load(name=f"RoboArm_{i+1}", power_kw=10, voltage=480, phases=3, power_factor=0.9, is_motor=True))
            
        # Total Connected Load (Amps):
        # 106.9 + (20 * 13.36) = 106.9 + 267.2 = 374.1 A
        
        # NEC Feeder Calculation (Standard):
        # 125% Largest Motor (106.9 * 0.25 = 26.725)
        # + Sum of all motors (374.1)
        # Total NEC = 400.8 A
        
        print(f"Total Connected Amps: 374.1 A")
        print(f"NEC Calculated Amps (No DF): 400.8 A")
        
        amps, cable, ref = calc.calculate_feeder_conductors(loads)
        self.assertAlmostEqual(amps, 400.8, delta=1.0)
        # 400A -> NEC Table 310.16 -> 600 kcmil (420A) or Parallel?
        # My logic: Try single first. 400.8 <= 420. So 600 kcmil.
        print(f"Selected Cable (Standard): {cable.size_awg} (Ref: {ref})")
        self.assertEqual(cable.size_awg, "600") 
        
        # 3. Apply User Demand Factor 70% (Engineer says diversity is high)
        user_df = 0.7
        amps_df, cable_df, ref_df = calc.calculate_feeder_conductors(loads, user_demand_factor=user_df)
        
        # 400.8 * 0.7 = 280.56 A
        # 280A -> 300 kcmil (285A)
        print(f"With 70% DF - Amps: {amps_df:.2f} A")
        print(f"Selected Cable (DF): {cable_df.size_awg} (Ref: {ref_df})")
        
        self.assertAlmostEqual(amps_df, 280.56, delta=1.0)
        self.assertEqual(cable_df.size_awg, "300") # 300kcmil is 285A

        # 4. Parallel Test: Increase load to force parallel
        # Add another Big Press
        loads.append(Load(name="Big Press 2", power_kw=200, voltage=480, phases=3, power_factor=0.9, is_motor=True))
        # New I = 200000/(480*1.732*0.9) = 267 A
        # Total Load approx 374 + 267 = 641 A
        # NEC Calc = 641 + 25% of 267 (Largest) = 641 + 66 = 707 A
        
        amps_par, cable_par, ref_par = calc.calculate_feeder_conductors(loads)
        print(f"Huge Load Amps: {amps_par:.2f} A")
        print(f"Selected Cable (Parallel): {ref_par}")
        
        # 707A > 420A (Max Single). Logic should pick 2 sets.
        # 707 / 2 = 353.5 A per set.
        # Check standard sizes >= 353.5A.
        # 500 kcmil = 380A. 
        # So should be 2x 500 kcmil.
        self.assertIn("2x 500 AWG/kcmil", ref_par)

if __name__ == '__main__':
    unittest.main()
