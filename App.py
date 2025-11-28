import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Cruces de archivos Excel", layout="wide")
st.title("📊 Cruce automático de archivos para parqueaderos")
st.write("Sube los tres archivos: **PQR.xlsx**, **CARTERA.xlsx** y **PARQ_ASIGNADOS.xlsx**, y el sistema realizará los cruces automáticamente.")

# === PASO 1: CARGA DE ARCHIVOS ===
pqr_file = st.file_uploader("📁 Cargar archivo PQR.xlsx", type=["xlsx"])
cartera_file = st.file_uploader("📁 Cargar archivo CARTERA.xlsx", type=["xlsx"])
parq_file = st.file_uploader("📁 Cargar archivo PARQ_ASIGNADOS.xlsx", type=["xlsx"])

if pqr_file and cartera_file and parq_file:
    st.success("✅ Archivos cargados correctamente. Procesando información...")

    # === PASO 2: PROCESAMIENTO ===

    # --- Leer PQR ---
    excel_file = pd.ExcelFile(pqr_file)
    dfs = []
    for sheet_name in excel_file.sheet_names:
        df = excel_file.parse(sheet_name)
        df["SheetName"] = sheet_name
        dfs.append(df)
    df_pqr = pd.concat(dfs, ignore_index=True)

    # Filtrar estados Autorizado y Solicitud
    dfpqr_filtered = df_pqr[df_pqr["Estado"].isin(["Autorizado", "Solicitud"])].copy()

    # --- Leer CARTERA ---
    excel_file_cartera = pd.ExcelFile(cartera_file)
    dfs_cartera = []
    for sheet_name in excel_file_cartera.sheet_names:
        df_cartera_sheet = excel_file_cartera.parse(sheet_name)
        df_cartera_sheet["SheetName"] = sheet_name
        # Filtrar columnas específicas (asegúrate de que existan)
        cols = ['codigo', 'propietari', 'saldo', 'cuotaparqu', 'vrcuota', 'moto', 'juridico', 'bicicleter']
        existing_cols = [c for c in cols if c in df_cartera_sheet.columns]
        df_cartera_filtered_sheet = df_cartera_sheet[existing_cols + ['SheetName']]
        dfs_cartera.append(df_cartera_filtered_sheet)

    df_cartera = pd.concat(dfs_cartera, ignore_index=True)

    # Calcular cal_cartera
    def calcular_cartera(row):
        try:
            return row['saldo'] - (row.get('vrcuota', 0) + row.get('cuotaparqu', 0) + row.get('moto', 0)) if row['saldo'] > 0 else 0
        except:
            return 0

    df_cartera["cal_cartera"] = df_cartera.apply(calcular_cartera, axis=1)

    # Concatenar campos clave
    dfpqr_filtered["Sheet_Codigo"] = dfpqr_filtered["SheetName"].astype(str) + "_" + dfpqr_filtered["Codigo"].astype(str)
    df_cartera["Sheet_Codigo"] = df_cartera["SheetName"].astype(str) + "_" + df_cartera["codigo"].astype(str)

    # Merge PQR + CARTERA
    dfpqr_filtered = pd.merge(
        dfpqr_filtered,
        df_cartera[
            ["Sheet_Codigo", "propietari", "saldo", "cuotaparqu", "vrcuota", "moto", "juridico", "bicicleter", "cal_cartera"]
        ],
        on="Sheet_Codigo",
        how="left"
    )

    # Asignar Parqueadero según condiciones
    def assign_park(row):
        if row["cal_cartera"] > 0 and row["juridico"] != "N":
            return "Revisar Acuerdo pago"
        elif row["cal_cartera"] > 10000 and row["juridico"] == "N":
            return "No"
        else:
            return "Si"

    dfpqr_filtered["Asignar_Park"] = dfpqr_filtered.apply(assign_park, axis=1)

    # --- Crear columna Concatenated_Info ---
    def concatenate_info(row):
        placa_moto = str(row.get("PlacaMoto", "")).strip()
        placa_carro = str(row.get("PlacaCarro", "")).strip()
        codigo = str(row.get("Codigo", "")).strip()
        sheet = str(row.get("SheetName", "")).strip()

        if placa_moto and placa_moto.lower() != "nan":
            return f"{codigo}_{placa_moto}_{sheet}"
        elif placa_carro and placa_carro.lower() != "nan":
            return f"{codigo}_{placa_carro}_{sheet}"
        else:
            return f"{codigo}_NoPlaca_{sheet}"

    dfpqr_filtered["Concatenated_Info"] = dfpqr_filtered.apply(concatenate_info, axis=1)

    # --- Leer PARQ_ASIGNADOS ---
    excel_file_parq = pd.ExcelFile(parq_file)
    dfs_parq = []
    for sheet_name in excel_file_parq.sheet_names:
        df_parq_sheet = excel_file_parq.parse(sheet_name)
        df_parq_sheet["SheetName"] = sheet_name
        dfs_parq.append(df_parq_sheet)
    df_parq_asignados = pd.concat(dfs_parq, ignore_index=True)

    # Limpiar y preparar PARQ_ASIGNADOS
    df_parq_asignados["Codigo"] = df_parq_asignados["Codigo"].fillna(0).astype(int)
    df_parq_asignados["Concatenated_Info"] = (
        df_parq_asignados["Codigo"].astype(str)
        + "_"
        + df_parq_asignados["PlacaVehiculo1"].astype(str)
        + "_"
        + df_parq_asignados["SheetName"]
    )

    # Separar columna Parqueadero
    if "Parqueadero" in df_parq_asignados.columns:
        df_parq_asignados[["Num_parq", "Tipo_parq"]] = df_parq_asignados["Parqueadero"].astype(str).str.split("-", expand=True)
    else:
        df_parq_asignados["Num_parq"] = ""
        df_parq_asignados["Tipo_parq"] = ""

    # Merge final
    dfpqr_filtered = pd.merge(
        dfpqr_filtered,
        df_parq_asignados[["Concatenated_Info", "Num_parq", "Tipo_parq"]],
        on="Concatenated_Info",
        how="left"
    )

    # Filtrar columnas específicas (asegúrate de que existan)
    cols = ['Codigo', 'Fecha', 'Estado', 'Respuesta', 'Destino', 'PlacaMoto', 'PlacaCarro', 'Color','SheetName','propietari','saldo','cuotaparqu','vrcuota','moto','bicicleter','juridico','cal_cartera','Asignar_Park','Num_parq','Tipo_parq']
    existing_cols = [c for c in cols if c in dfpqr_filtered.columns]
    dfpqr_filtered = dfpqr_filtered[existing_cols + ['SheetName']]
    dfpqr_filtered.append(df_cartera_filtered_sheet)


    st.subheader("📋 Vista previa de los resultados")
    st.dataframe(dfpqr_filtered.head(20))

    # === PASO 3: DESCARGAR RESULTADO ===
    output = BytesIO()
    dfpqr_filtered.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        label="⬇️ Descargar resultado (Excel)",
        data=output,
        file_name="dfpqr_filtered.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Por favor, sube los tres archivos para comenzar el procesamiento.")




