import unittest
from core.components import Load
from standards.iec import IECCalculator
from standards.nec import NECCalculator

class TestCalculations(unittest.TestCase):
    def test_iec_calculation(self):
        calc = IECCalculator()
        # 10kW, 400V, 3-phase, PF 0.9
        # Ib = 10000 / (400 * 1.732 * 0.9) = 16.03 A
        load = Load(name="Motor", power_kw=10, voltage=400, phases=3, power_factor=0.9)
        breaker, cable, ref = calc.calculate_circuit(load)
        
        # Should select 20A breaker (next standard size > 16.03)
        self.assertEqual(breaker.rated_current, 20)
        # Cable for 20A breaker -> 2.5mm2 (24A capacity)
        self.assertEqual(cable.size_mm2, 2.5)
        self.assertIn("IEC", ref)

    def test_nema_calculation(self):
        calc = NECCalculator()
        # 5kW, 220V, 1-phase, PF 0.9, Continuous
        # Ib = 5000 / (220 * 0.9) = 25.25 A
        # Required = 25.25 * 1.25 = 31.56 A
        load = Load(name="Heater", power_kw=5, voltage=220, phases=1, power_factor=0.9, is_continuous=True)
        breaker, cable, ref = calc.calculate_circuit(load)
        
        # Should select 35A breaker (next standard size > 31.56)
        self.assertEqual(breaker.rated_current, 35)
        self.assertIn("NEC", ref)

    def test_nec_feeder(self):
        calc = NECCalculator()
        # Load 1: Motor, 10kW, 400V 3Ph (approx 16A) -> FLA
        # Load 2: Heater, 10kW, 400V 3Ph (approx 16A) -> Continuous
        
        l1 = Load(name="Motor1", power_kw=10, voltage=400, phases=3, power_factor=0.9, is_motor=True)
        l2 = Load(name="Heater1", power_kw=10, voltage=400, phases=3, power_factor=0.9, is_continuous=True)
        
        # Ib L1 = 16.03 A
        # Ib L2 = 16.03 A
        
        # NEC Feeder Rule:
        # Sum of non-continuous loads + 125% of continuous + 125% largest motor + sum other motors
        # Here: 1 Motor (Largest) -> 16.03 * 1.25 = 20.04
        # Other Motors -> 0
        # Continuous -> 16.03 * 1.25 = 20.04
        # Total = 40.08 A
        
        feeder_amps, cable, ref = calc.calculate_feeder_conductors([l1, l2])
        self.assertAlmostEqual(feeder_amps, 40.08, delta=0.5)
        self.assertIn("Largest Motor", ref)
        # Total 40A > 35A (10 AWG), so needs 8 AWG (50A)
        self.assertEqual(cable.size_awg, "8")
        
        # Grounding Test
        # Breaker likely based on Max allowed or Ampacity.
        # Ampacity 50A. Breaker could be 50A or up to 250% motor... let's check calculate_main_protection
        main_breaker, mb_ref = calc.calculate_main_protection([l1, l2], cable)
        # Main breaker for 50A cable -> likely 50A or 60A allowed? Strict <= Iz says 50A.
        
        grounding, g_ref = calc.calculate_grounding_conductor(cable, main_breaker)
        # For 50A breaker -> NEC Table 250.122 says 10 AWG (up to 60A).
        self.assertEqual(grounding.size_awg, "10")
        self.assertIn("NEC 250.122", g_ref)

if __name__ == '__main__':
    unittest.main()
