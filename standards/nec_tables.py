from core.models import ConductorMaterial, InsulationRating, ConduitType

# NEC Table 310.15(B)(1) - Ambient Temperature Correction Factors
# Based on 30°C base ambient
# Format: {Temp_Range_Tuple: {Insulation_Rating: Factor}}
TEMP_CORRECTION_FACTORS = {
    (0, 10): {60: 1.29, 75: 1.20, 90: 1.15},
    (11, 15): {60: 1.22, 75: 1.15, 90: 1.12},
    (16, 20): {60: 1.15, 75: 1.11, 90: 1.08},
    (21, 25): {60: 1.08, 75: 1.05, 90: 1.04},
    (26, 30): {60: 1.00, 75: 1.00, 90: 1.00},
    (31, 35): {60: 0.91, 75: 0.94, 90: 0.96},
    (36, 40): {60: 0.82, 75: 0.88, 90: 0.91},
    (41, 45): {60: 0.71, 75: 0.82, 90: 0.87},
    (46, 50): {60: 0.58, 75: 0.75, 90: 0.82},
    (51, 55): {60: 0.41, 75: 0.67, 90: 0.76},
    (56, 60): {60: 0.00, 75: 0.58, 90: 0.71},
    (61, 70): {60: 0.00, 75: 0.47, 90: 0.65},
}

# NEC Table 310.15(C)(1) - Adjustment Factors for More Than Three Current-Carrying Conductors
# Format: {Max_Conductors: Factor}
GROUPING_FACTORS = {
    3: 1.0,
    6: 0.80,   # 4-6 conductors
    9: 0.70,   # 7-9
    20: 0.50,  # 10-20
    30: 0.45,  # 21-30
    40: 0.40,  # 31-40
    100: 0.35  # 41+
}

# NEC Table 310.16 - Allowable Ampacities of Insulated Conductors
# Simplified for Copper, 75C and 90C (Most common)
# Format: {SizeAWG: {TempRating: Amps}}
NEC_310_16_COPPER = {
    "14": {60: 15, 75: 20, 90: 25},
    "12": {60: 20, 75: 25, 90: 30},
    "10": {60: 30, 75: 35, 90: 40},
    "8":  {60: 40, 75: 50, 90: 55},
    "6":  {60: 55, 75: 65, 90: 75},
    "4":  {60: 70, 75: 85, 90: 95},
    "3":  {60: 85, 75: 100, 90: 115},
    "2":  {60: 95, 75: 115, 90: 130},
    "1":  {60: 110, 75: 130, 90: 145},
    "1/0": {60: 125, 75: 150, 90: 170},
    "2/0": {60: 145, 75: 175, 90: 195},
    "3/0": {60: 165, 75: 200, 90: 225},
    "4/0": {60: 195, 75: 230, 90: 260},
    "250": {60: 215, 75: 255, 90: 290},
    "300": {60: 240, 75: 285, 90: 320},
    "350": {60: 260, 75: 310, 90: 350},
    "400": {60: 280, 75: 335, 90: 380},
    "500": {60: 320, 75: 380, 90: 430},
    "600": {60: 350, 75: 420, 90: 475},
    "700": {60: 385, 75: 460, 90: 520},
    "750": {60: 400, 75: 475, 90: 535},
    "800": {60: 410, 75: 490, 90: 555},
    "900": {60: 435, 75: 520, 90: 585},
    "1000": {60: 455, 75: 545, 90: 615},
    "1250": {60: 495, 75: 590, 90: 665},
    "1500": {60: 525, 75: 625, 90: 705},
    "1750": {60: 545, 75: 650, 90: 735},
    "2000": {60: 555, 75: 665, 90: 750},
}

# NEC Chapter 9, Table 9 - AC Resistance and Reactance for 600V Cables (Ohms to Neutral per 1000 ft)
# Key: (SizeAWG, ConduitType) -> (R, X)
# Simplified for Copper Conductors in PVC and Steel
# R is AC Resistance at 75C, X is Reactance
TABLE_9_IMPEDANCE = {
    # Size: {PVC: (R, X), STEEL: (R, X)}
    "14": {ConduitType.PVC: (3.1, 0.048), ConduitType.STEEL: (3.1, 0.060)},
    "12": {ConduitType.PVC: (2.0, 0.046), ConduitType.STEEL: (2.0, 0.057)},
    "10": {ConduitType.PVC: (1.2, 0.044), ConduitType.STEEL: (1.2, 0.055)},
    "8":  {ConduitType.PVC: (0.78, 0.052), ConduitType.STEEL: (0.78, 0.066)},
    "6":  {ConduitType.PVC: (0.49, 0.051), ConduitType.STEEL: (0.49, 0.063)},
    "4":  {ConduitType.PVC: (0.31, 0.048), ConduitType.STEEL: (0.31, 0.059)},
    "3":  {ConduitType.PVC: (0.25, 0.047), ConduitType.STEEL: (0.25, 0.058)},
    "2":  {ConduitType.PVC: (0.19, 0.045), ConduitType.STEEL: (0.20, 0.057)},
    "1":  {ConduitType.PVC: (0.15, 0.046), ConduitType.STEEL: (0.16, 0.057)},
    "1/0": {ConduitType.PVC: (0.12, 0.044), ConduitType.STEEL: (0.13, 0.055)},
    "2/0": {ConduitType.PVC: (0.10, 0.043), ConduitType.STEEL: (0.10, 0.054)},
    "3/0": {ConduitType.PVC: (0.077, 0.042), ConduitType.STEEL: (0.082, 0.052)},
    "4/0": {ConduitType.PVC: (0.062, 0.041), ConduitType.STEEL: (0.067, 0.051)},
    "250": {ConduitType.PVC: (0.052, 0.041), ConduitType.STEEL: (0.054, 0.052)},
    "300": {ConduitType.PVC: (0.044, 0.041), ConduitType.STEEL: (0.045, 0.051)},
    "350": {ConduitType.PVC: (0.038, 0.040), ConduitType.STEEL: (0.039, 0.050)},
    "400": {ConduitType.PVC: (0.033, 0.040), ConduitType.STEEL: (0.035, 0.049)},
    "500": {ConduitType.PVC: (0.027, 0.039), ConduitType.STEEL: (0.029, 0.048)},
    "600": {ConduitType.PVC: (0.023, 0.039), ConduitType.STEEL: (0.025, 0.048)},
}

def get_temp_correction(temp_c: float, insulation_rating: int) -> float:
    for (min_t, max_t), distinct_ratings in TEMP_CORRECTION_FACTORS.items():
        if min_t <= temp_c <= max_t:
            return distinct_ratings.get(insulation_rating, 1.0)
    if temp_c <= 20: return 1.0 # Simple assumption
    if temp_c >= 71: return 0.0 # Too hot
    return 1.0

def get_grouping_factor(count: int) -> float:
    # Find match
    prev_limit = 0
    for limit in sorted(GROUPING_FACTORS.keys()):
        if count <= limit:
            return GROUPING_FACTORS[limit]
    return 0.35 # Fallback
