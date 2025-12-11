import streamlit as st
import pandas as pd
import math
from core.models import LoadInput, InstallationParams, ConduitType, ConductorMaterial, InsulationRating
from core.converters import convert_power_unit, convert_length_unit
from standards.nec_logic import NECLogic
from standards.nec_tables import NEC_310_16_COPPER
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# --- Page Config ---
st.set_page_config(
    page_title="Calculadora de Tableros (NEC)",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .main-header { font-family: 'Inter', sans-serif; color: #1E3A8A; font-weight: 700; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'loads' not in st.session_state:
    st.session_state.loads = []

# --- Sidebar: Global Settings ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=60)
    st.title("Configuración Global")
    
    st.markdown("### 🌡️ Condiciones Ambientales")
    st.info("La temperatura ambiente aplica globalmente. El tipo de ducto se define por carga.")
    temp_env = st.number_input("Temperatura Ambiente (°C)", value=30.0, step=1.0, min_value=-50.0, max_value=120.0, help="NEC Tabla 310.15(B)(1)")

# --- Main Area ---
st.markdown("<h1 class='main-header'>⚡ Calculadora de Circuitos (NEC Edition)</h1>", unsafe_allow_html=True)
st.markdown("---")

col1, col2 = st.columns([1, 2])

# --- Section 1: Add New Load ---
with col1:
    with st.container():
        st.subheader("➕ Agregar Carga")
        with st.form("add_load_form", clear_on_submit=False):
            name = st.text_input("Nombre de Carga", placeholder="Ej. Motor Bomba 1")
            
            c1, c2 = st.columns(2)
            with c1:
                qty = st.number_input("Cantidad", min_value=1, value=1, step=1)
            with c2:
                phases = st.radio("Fases", [1, 3], horizontal=True)
            
            c3, c4 = st.columns([2, 1])
            with c3:
                power_val = st.number_input("Potencia", min_value=0.0, value=0.0, step=0.1)
            with c4:
                power_unit = st.selectbox("Unidad", ["W", "KW", "HP", "A", "KVA"])
                
            voltage = st.number_input("Voltaje (V)", value=220.0 if phases==1 else 480.0, step=10.0)
            pf = st.number_input("Factor de Potencia", value=0.9, min_value=0.1, max_value=1.0, step=0.05)
            
            # Installation specifics
            st.markdown("**Detalles del Circuito Derivado**")
            length_val = st.number_input("Longitud", value=10.0)
            length_unit = st.selectbox("Unidad Long.", ["m", "ft"], index=0)
            
            # Advanced NEC
            with st.expander("Opciones Avanzadas (NEC)", expanded=True):
                is_motor = st.checkbox("Es Motor", value=False)
                is_continuous = st.checkbox("Carga Continua (>3h)", value=False)
                
                st.markdown("---")
                st.markdown("**Parámetros de Instalación**")
                
                # Conduit Selection (Moved Here)
                conduit_options = {
                    "PVC (No Magnético)": ConduitType.PVC,
                    "Acero (Magnético)": ConduitType.STEEL,
                    "Aluminio": ConduitType.ALUMINUM
                }
                conduit_label = st.selectbox("Tipo de Ducto", list(conduit_options.keys()))
                local_conduit = conduit_options[conduit_label]
                
                temp_rating_choice = st.radio("Temp. Aislamiento", ["75°C (THWN)", "90°C (THHN/THWN-2)"])
                rating_enum = InsulationRating.TEMP_90 if "90" in temp_rating_choice else InsulationRating.TEMP_75
                
                grouping_count = st.number_input("Total Conductores en Ducto", min_value=1, value=3, help="Para corrección NEC 310.15(C)(1)")
            
            submitted = st.form_submit_button("Agregar Carga", type="primary")
            
            if submitted:
                if name:
                    watts, amps_override = convert_power_unit(power_val, power_unit, voltage, phases, pf)
                    length_m = convert_length_unit(length_val, length_unit)
                    
                    load_obj = LoadInput(
                        name=name, power_watts=watts, voltage=voltage, phases=phases,
                        is_continuous=is_continuous, is_motor=is_motor, power_factor=pf,
                        quantity=qty, override_amps=amps_override
                    )
                    
                    inst_params = InstallationParams(
                        length_meters=length_m,
                        conduit_type=local_conduit, # Usar valor local
                        ambient_temp_c=temp_env,    # Valor global inicial
                        raceway_count=grouping_count,
                        conductor_material=ConductorMaterial.COPPER,
                        insulation_rating=rating_enum
                    )
                    
                    st.session_state.loads.append({"load": load_obj, "params": inst_params})
                    st.success(f"Carga '{name}' agregada.")
                else:
                    st.error("El nombre es obligatorio.")

# --- Section 2: Results Table ---
with col2:
    st.subheader("📋 Tabla de Cargas y Resultados")
    
    if not st.session_state.loads:
        st.info("No hay cargas agregadas. Utilice el formulario de la izquierda.")
    else:
        results_data = []
        feeder_loads = []
        
        for i, item in enumerate(st.session_state.loads):
            l = item["load"]
            p = item["params"]
            
            # Update Global Ambient Temp only
            p.ambient_temp_c = temp_env
            # DO NOT override conduit type here, respecting individual choice
            
            res = NECLogic.select_conductor_and_breaker(l, p)
            
            if l.override_amps:
                disp_amps = l.override_amps
            else:
                 if l.phases == 1:
                    disp_amps = l.power_watts / (l.voltage * l.power_factor)
                 else:
                    disp_amps = l.power_watts / (math.sqrt(3) * l.voltage * l.power_factor)
            
            # Determine conduit label for display
            c_disp = "PVC"
            if p.conduit_type == ConduitType.STEEL: c_disp = "Acero"
            elif p.conduit_type == ConduitType.ALUMINUM: c_disp = "Alum"
            
            results_data.append({
                "Cant": l.quantity,
                "Nombre": l.name,
                "Potencia": f"{l.power_watts:.0f} W" if l.power_watts < 1000 else f"{l.power_watts/1000:.1f} KW",
                "Voltaje": l.voltage,
                "Amps (I)": round(disp_amps, 1),
                "Calibre": res.size,
                "Ampacidad": res.ampacity,
                "Breaker": res.breaker_rating,
                "% VD": float(f"{res.voltage_drop_percent:.2f}"),
                "Ducto": c_disp,
                "Temp Rat": f"{p.insulation_rating.value}°C"
            })
            
            feeder_loads.append(l)

        df = pd.DataFrame(results_data)
        
        st.dataframe(
            df.style.map(lambda x: 'color: red; font-weight: bold' if isinstance(x, float) and x > 3.0 else '', subset=['% VD']),
            use_container_width=True,
            hide_index=True
        )
        
        if st.button("🗑️ Limpiar Todo", type="secondary"):
            st.session_state.loads = []
            st.rerun()

# --- Section 3: Main Feeder ---
st.markdown("---")
st.subheader("🏢 Alimentador Principal (Main Feeder)")

if st.session_state.loads:
    feeder_res = NECLogic.calculate_main_feeder(feeder_loads)
    
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Corriente Total Est.", f"{feeder_res['total_amps']:.1f} A")
    with m2:
        st.metric("Conductor Sugerido", feeder_res['cable_size'])
    with m3:
        runs = feeder_res['parallel_runs']
        desc = feeder_res['description']
        st.metric("Configuración", "Simple" if runs==1 else f"{runs}x Paralelo", delta=desc, delta_color="off")
    
    st.info(f"**Nota:** Cálculo basado en NEC 430.24 (Motores) y 215.2 (Continuo + Demand). {feeder_res['description']}")

# --- Section 4: Export ---
def generate_excel():
    output = io.BytesIO()
    wb = Workbook()
    
    # Sheet 1: Branch Circuits
    ws = wb.active
    ws.title = "Circuitos Derivados"
    ws.append(["Cant", "Nombre", "Potencia W", "Voltaje", "Fases", "Amps", "Calibre", "Ampacidad", "Breaker", "% VD", "Tipo Ducto", "Notas"])
    
    for i, item in enumerate(st.session_state.loads):
        l = item["load"]
        p = item["params"]
        r = NECLogic.select_conductor_and_breaker(l, p)
        
        if l.override_amps:
            a = l.override_amps
        else:
             a = l.power_watts / (l.voltage * (1.732 if l.phases==3 else 1) * l.power_factor)
             
        ws.append([l.quantity, l.name, l.power_watts, l.voltage, l.phases, round(a,2), r.size, r.ampacity, r.breaker_rating, r.voltage_drop_percent, p.conduit_type.value, r.reference_notes])

    # Sheet 2: Feeder
    if st.session_state.loads:
        ws2 = wb.create_sheet("Alimentador")
        fres = NECLogic.calculate_main_feeder([item["load"] for item in st.session_state.loads])
        ws2.append(["Parametro", "Valor"])
        ws2.append(["Total Amps", fres['total_amps']])
        ws2.append(["Cable", fres['cable_size']])
        ws2.append(["Config", fres['description']])

    wb.save(output)
    return output.getvalue()

if st.session_state.loads:
    excel_data = generate_excel()
    st.download_button(
        label="📥 Descargar Reporte Excel",
        data=excel_data,
        file_name="memoria_calculo_nec_v2.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
