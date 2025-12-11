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
    .stDataFrame { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# --- Session State Init ---
INPUT_COLUMNS = [
    "Nombre", "Qty", "Potencia", "Unidad", "Voltaje", "Fases", "FP", 
    "Longitud", "U.Long", "EsMotor", "EsContinuo", 
    "T.Amb", "Ducto", "Rating", "Agrupamiento", "CalculatedAmpsOverride"
]

if 'loads_df' not in st.session_state:
    st.session_state.loads_df = pd.DataFrame(columns=INPUT_COLUMNS)
else:
    # Sanitation Check: Ensure no duplicate columns from previous hot-reloads
    st.session_state.loads_df = st.session_state.loads_df.loc[:, ~st.session_state.loads_df.columns.duplicated()]
    # Ensure only input columns exist
    existing_cols = [c for c in INPUT_COLUMNS if c in st.session_state.loads_df.columns]
    st.session_state.loads_df = st.session_state.loads_df[existing_cols]
    
    # Missing columns fill?
    for col in INPUT_COLUMNS:
        if col not in st.session_state.loads_df.columns:
            st.session_state.loads_df[col] = None

if "voltage_input" not in st.session_state:
    st.session_state.voltage_input = 480.0

def on_phase_change():
    if st.session_state.phases_input == 1:
        st.session_state.voltage_input = 220.0
    else:
        st.session_state.voltage_input = 480.0

# --- Helper: Calculate Row ---
def calculate_row_results(row):
    # Convert Row to Objects
    try:
        # Power Unit Logic is complex because we need original val and unit.
        # But we stored them. Recalculate watts.
        # Wait, if user edits "Potencia" in table (e.g. 10 -> 15), we need to recalibrate.
        
        watts, amps_ovr = convert_power_unit(
            float(row["Potencia"]), row["Unidad"], 
            float(row["Voltaje"]), int(row["Fases"]), float(row["FP"])
        )
        
        len_m = convert_length_unit(float(row["Longitud"]), row["U.Long"])
        
        # Conduit Map
        c_str = str(row["Ducto"])
        c_type = ConduitType.PVC
        if "Acero" in c_str or "STEEL" in c_str.upper(): c_type = ConduitType.STEEL
        elif "Alum" in c_str or "ALUMINUM" in c_str.upper(): c_type = ConduitType.ALUMINUM
            
        # Insul Map
        r_val = int(str(row["Rating"]).replace("C","").replace("°",""))
        r_enum = InsulationRating.TEMP_90 if r_val == 90 else InsulationRating.TEMP_75
        
        load_obj = LoadInput(
            name=str(row["Nombre"]),
            power_watts=watts,
            voltage=float(row["Voltaje"]),
            phases=int(row["Fases"]),
            is_continuous=bool(row["EsContinuo"]),
            is_motor=bool(row["EsMotor"]),
            power_factor=float(row["FP"]),
            quantity=int(row["Qty"]),
            override_amps=amps_ovr
        )
        
        inst_params = InstallationParams(
            length_meters=len_m,
            conduit_type=c_type,
            ambient_temp_c=float(row["T.Amb"]),
            raceway_count=int(row["Agrupamiento"]),
            conductor_material=ConductorMaterial.COPPER,
            insulation_rating=r_enum
        )
        
        res = NECLogic.select_conductor_and_breaker(load_obj, inst_params)
        
        # Display Amps
        if amps_ovr:
            d_amps = amps_ovr
        else:
             if load_obj.phases == 1:
                d_amps = load_obj.power_watts / (load_obj.voltage * load_obj.power_factor)
             else:
                d_amps = load_obj.power_watts / (math.sqrt(3) * load_obj.voltage * load_obj.power_factor)

        return pd.Series({
            "I (Amps)": round(d_amps, 1),
            "Calibre": res.size,
            "Ampacidad": res.ampacity,
            "Breaker": res.breaker_rating,
            "% VD": float(f"{res.voltage_drop_percent:.2f}"),
            "Notas": res.reference_notes,
            "_load_obj": load_obj # Store for feeder calc (hidden)
        })
    except Exception as e:
        return pd.Series({"Notas": f"Error: {str(e)}"})

# --- Helper: Export Excel ---
def to_excel(df, feeder_data=None):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Detail
        cols_to_export = [c for c in df.columns if c != "_load_obj" and c != "CalculatedAmpsOverride"]
        df[cols_to_export].to_excel(writer, index=False, sheet_name='Circuitos')
        
        # Sheet 2: Feeder
        if feeder_data:
            f_df = pd.DataFrame([
                {"Parametro": "Total Amps Estimado", "Valor": feeder_data['total_amps']},
                {"Parametro": "Conductor Alimentador Sugerido", "Valor": feeder_data['cable_size']},
                {"Parametro": "Configuración", "Valor": feeder_data['description']},
                {"Parametro": "Runs Paralelos", "Valor": feeder_data['parallel_runs']}
            ])
            f_df.to_excel(writer, index=False, sheet_name='Alimentador')
            
    return output.getvalue()

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=60)
    st.title("Configuración")
    st.info("Ahora puede editar todos los datos directamente en la tabla principal.")
    
    st.markdown("---")
    st.subheader("📥 Importación Masiva")
    
    # 1. Download Template
    def get_template():
        data = {
            "Nombre": ["Motor Bomba", "Iluminación Hall"],
            "Cantidad": [1, 15],
            "Potencia": [10, 100],
            "UnidadPotencia": ["HP", "W"],
            "Voltaje": [480, 220],
            "Fases": [3, 1],
            "FP": [0.85, 0.95],
            "Longitud": [50, 20],
            "UnidadLongitud": ["m", "m"],
            "EsMotor": ["SI", "NO"],
            "EsContinuo": ["NO", "SI"],
            "TempAmb": [30, 30],
            "TipoDucto": ["ACERO", "PVC"],
            "Rating": [75, 90],
            "Agrupamiento": [3, 3]
        }
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Plantilla')
        return output.getvalue()
        
    st.download_button(
        "📄 Descargar Plantilla Excel",
        data=get_template(),
        file_name="plantilla_cargas_nec.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Descargue esta plantilla, llénela y súbala."
    )
    
    # 2. Upload File
    uploaded_file = st.file_uploader("Subir Excel", type=["xlsx"])
    
    if uploaded_file:
        if st.button("Procesar Archivo"):
            try:
                df_in = pd.read_excel(uploaded_file)
                new_rows = []
                
                for idx, row in df_in.iterrows():
                    # Map Excel columns to App DataFrame Columns
                    # Flexible reading
                    try:
                        n_row = {
                            "Nombre": str(row.get("Nombre", "Carga")),
                            "Qty": int(row.get("Cantidad", 1)),
                            "Potencia": float(row.get("Potencia", 0)),
                            "Unidad": str(row.get("UnidadPotencia", "W")).strip(),
                            "Voltaje": float(row.get("Voltaje", 220)),
                            "Fases": int(row.get("Fases", 1)),
                            "FP": float(row.get("FP", 0.9)),
                            "Longitud": float(row.get("Longitud", 10)),
                            "U.Long": str(row.get("UnidadLongitud", "m")).strip(),
                            "EsMotor": str(row.get("EsMotor", "NO")).upper() == "SI",
                            "EsContinuo": str(row.get("EsContinuo", "NO")).upper() == "SI",
                            "T.Amb": float(row.get("TempAmb", 30)),
                            "Ducto": "Acero" if "ACERO" in str(row.get("TipoDucto", "")).upper() or "STEEL" in str(row.get("TipoDucto", "")).upper() else ("Aluminio" if "ALUM" in str(row.get("TipoDucto", "")).upper() else "PVC"),
                            "Rating": int(row.get("Rating", 75)),
                            "Agrupamiento": int(row.get("Agrupamiento", 3)),
                            "CalculatedAmpsOverride": None
                        }
                        new_rows.append(n_row)
                    except Exception as e:
                        st.error(f"Error parseando fila {idx+2}: {e}")
                
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    # Align columns just in case
                    st.session_state.loads_df = pd.concat([st.session_state.loads_df, new_df], ignore_index=True)
                    st.success(f"✅ {len(new_rows)} cargas importadas.")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error procesando archivo: {e}")
        
# --- Main Area ---
st.markdown("<h1 class='main-header'>⚡ Calculadora de Circuitos (NEC Edition v2.3)</h1>", unsafe_allow_html=True)
st.markdown("---")

# Input Form (Clean Layout)
with st.expander("➕ Agregar Nueva Carga", expanded=True):
    # Row 1: Identificación
    c_name, c_qty = st.columns([3, 1])
    name = c_name.text_input("Nombre de la Carga", "Carga 1")
    qty = c_qty.number_input("Cantidad", 1, 100, 1, help="Multiplicador")

    st.markdown("##### ⚡ Datos Eléctricos")
    # Row 2: Potencia Compleja y Voltaje
    c_p1, c_p2, c_v1, c_v2, c_fp = st.columns([1.5, 0.8, 1.2, 0.8, 1])
    power = c_p1.number_input("Potencia", 0.0, step=0.1, format="%.2f")
    unit = c_p2.selectbox("Unidad", ["W", "KW", "HP", "A", "KVA"], label_visibility="visible")
    
    voltage = c_v1.number_input("Voltaje (V)", step=10, key="voltage_input")
    phases = c_v2.radio("Fases", [1, 3], horizontal=True, key="phases_input", on_change=on_phase_change)
    pf = c_fp.number_input("FP", 0.1, 1.0, 0.9, 0.05)

    # Row 3: Flags
    c_flags = st.columns(4)
    is_motor = c_flags[0].toggle("Es Motor", False)
    is_cont = c_flags[1].toggle("Carga Continua", False)

    st.markdown("##### 📏 Instalación y Ambiente")
    # Row 4: Física
    c_L1, c_L2, c_T1, c_T2 = st.columns([1.5, 0.8, 1.2, 1])
    length = c_L1.number_input("Longitud", 1.0, step=1.0)
    l_unit = c_L2.selectbox("U.Long", ["m", "ft"])
    temp = c_T1.number_input("Temp. Amb (°C)", value=30.0, step=1.0)
    rating = c_T2.selectbox("Aislamiento", ["75", "90"])

    # Row 5: Ducto
    c_D1, c_D2 = st.columns([2, 1])
    duct = c_D1.selectbox("Tipo de Ducto", ["PVC", "Acero", "Aluminio"])
    group = c_D2.number_input("Agrupamiento (Cables en ducto)", 1, 40, 3)

    st.write("") # Spacer
    if st.button("Agregar a Tabla", type="primary", use_container_width=True):
        new_row = {
            "Nombre": name, "Qty": qty, "Potencia": power, "Unidad": unit, 
            "Voltaje": voltage, "Fases": phases, "FP": pf,
            "Longitud": length, "U.Long": l_unit, 
            "EsMotor": is_motor, "EsContinuo": is_cont,
            "T.Amb": temp, "Ducto": duct, "Rating": int(rating), "Agrupamiento": group,
            "CalculatedAmpsOverride": None
        }
        st.session_state.loads_df = pd.concat([st.session_state.loads_df, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

st.markdown("### 📋 Tabla Maestra de Cargas (Editable)")

# Toolbar
tb1, tb2, tb3 = st.columns([1, 1, 4])
with tb1:
    if st.button("🗑️ Borrar Tabla", type="secondary", use_container_width=True):
        st.session_state.loads_df = pd.DataFrame(columns=INPUT_COLUMNS)
        st.rerun()
with tb2:
    # Prepare export data eagerly for the button logic
    # Note: To export fully calculated data, we need the df_full from below. 
    # But streamlining, we can recalculate or wait.
    # Actually, we can just use the button below or duplicate logic.
    # To avoid double calc, we will render this button AFTER calc but using columns container trick or just place it below header.
    # Since download_button needs data content immediately, let's defer rendering until we have df_full.
    pass

st.caption("Edite cualquier celda para recalcular. Seleccione filas y presione 'Supr'/Delete para eliminar.")

# Prepare Data for Editor
df_to_show = st.session_state.loads_df.copy()

# Apply Calculations
if not df_to_show.empty:
    results = df_to_show.apply(calculate_row_results, axis=1)
    df_full = pd.concat([df_to_show, results], axis=1)
else:
    result_cols = ["I (Amps)", "Calibre", "Ampacidad", "Breaker", "% VD", "Notas", "_load_obj"]
    df_results_empty = pd.DataFrame(columns=result_cols)
    df_full = pd.concat([df_to_show, df_results_empty], axis=1)

# Toolbar Part 2 (Now we have data)
with tb2:
     if not df_full.empty:
        st.download_button(
            "📥 Excel",
            data=to_excel(df_full), # Simplified call, Feeder calc is later, maybe pass None or quick calc?
            # User wants to download TABLE. Maybe just table? 
            # Or wait... st.download_button reruns script? No.
            file_name="tabla_cargas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# Configure Columns
column_config = {
    "Qty": st.column_config.NumberColumn("Cant", min_value=1, step=1, width="small"),
    "Potencia": st.column_config.NumberColumn(min_value=0, step=0.1, format="%.1f"),
    "Unidad": st.column_config.SelectboxColumn(options=["W", "KW", "HP", "A", "KVA"], width="small"),
    "Voltaje": st.column_config.NumberColumn(step=10),
    "Fases": st.column_config.SelectboxColumn(options=[1, 3], width="small"),
    "Ducto": st.column_config.SelectboxColumn(options=["PVC", "Acero", "Aluminio"], width="medium"),
    "Rating": st.column_config.SelectboxColumn(options=[75, 90], width="small"),
    "U.Long": st.column_config.SelectboxColumn(options=["m", "ft"], width="small"),
    "_load_obj": None, # Hide
    "CalculatedAmpsOverride": None # Hide
}

# Output columns should be disabled
disabled_cols = ["I (Amps)", "Calibre", "Ampacidad", "Breaker", "% VD", "Notas"]

edited_df = st.data_editor(
    df_full,
    key="editor",
    use_container_width=True,
    num_rows="dynamic",
    column_config=column_config,
    disabled=disabled_cols,
    height=400
)

# Detect Changes
# Logic: If edited_df differs from st.session_state.loads_df (ignoring result cols), update session state
# Filter input columns only
edited_inputs = edited_df[INPUT_COLUMNS]

# We verify if we need to update session state (if inputs changed)
if not edited_inputs.equals(st.session_state.loads_df):
    st.session_state.loads_df = edited_inputs
    st.rerun() # Rerun to recalculate results if needed

# --- Feeder Section ---
st.markdown("---")
st.subheader("🏢 Alimentador Total")

# Extract Load Objects from 'df_full'
feeder_loads_list = []
if "_load_obj" in df_full.columns:
    feeder_loads_list = df_full["_load_obj"].dropna().tolist()

if feeder_loads_list:
    feeder_res = NECLogic.calculate_main_feeder(feeder_loads_list)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Amps", f"{feeder_res['total_amps']:.1f} A")
    c2.metric("Cable Feeder", feeder_res['cable_size'])
    c3.metric("Config", feeder_res['description'])

# --- Export Selection ---
def to_excel(df, feeder_data):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Detail
        cols_to_export = [c for c in df.columns if c != "_load_obj" and c != "CalculatedAmpsOverride"]
        df[cols_to_export].to_excel(writer, index=False, sheet_name='Circuitos')
        
        # Sheet 2: Feeder
        if feeder_data:
            f_df = pd.DataFrame([
                {"Parametro": "Total Amps Estimado", "Valor": feeder_data['total_amps']},
                {"Parametro": "Conductor Alimentador Sugerido", "Valor": feeder_data['cable_size']},
                {"Parametro": "Configuración", "Valor": feeder_data['description']},
                {"Parametro": "Runs Paralelos", "Valor": feeder_data['parallel_runs']}
            ])
            f_df.to_excel(writer, index=False, sheet_name='Alimentador')
            
    return output.getvalue()

if not df_full.empty:
    excel_data = to_excel(df_full, feeder_res if 'feeder_res' in locals() else None)
    st.download_button(
        "📥 Descargar Resultados (Excel)",
        data=excel_data,
        file_name="memoria_nec_v2_3.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Descarga la tabla completa y el cálculo del alimentador."
    )
