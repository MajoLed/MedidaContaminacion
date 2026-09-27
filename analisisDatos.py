import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# CONFIGURACIÓN
# ============================================================

RUTA_DATOS = Path("mediciones")
SALIDA = Path("resultados")
SALIDA.mkdir(exist_ok=True)

N_ESPECTRO = 1024
N_META = 5
N_COLUMNAS = N_ESPECTRO + N_META

F_MIN = 840.0
F_MAX = 860.0

UMBRAL_CONTAMINACION = -60.0

COLUMNAS_ESPECTRO = [
    f"espectro_{i+1}" for i in range(N_ESPECTRO)
]

COLUMNAS_META = [
    "temperatura",
    "longitud",
    "latitud",
    "altitud",
    "error_distancia"
]

COLUMNAS = COLUMNAS_ESPECTRO + COLUMNAS_META

frecuencias = np.linspace(F_MIN, F_MAX, N_ESPECTRO)


# ============================================================
# 1. LECTURA Y UNIFICACIÓN DE ARCHIVOS
# ============================================================

print("=== 1. UNIFICANDO ARCHIVOS DE DATOS ===")

archivos = sorted(RUTA_DATOS.glob("*.txt"))

if not archivos:
    raise FileNotFoundError(
        f"No se encontraron archivos .txt en '{RUTA_DATOS}'."
    )

frames = []

for archivo in archivos:
    try:
        df_temp = pd.read_csv(
            archivo,
            sep=",",
            header=None,
            skip_blank_lines=True,
            on_bad_lines="error"
        )

        if df_temp.empty:
            print(f"Advertencia: archivo vacío: {archivo.name}")
            continue

        if df_temp.shape[1] < N_COLUMNAS:
            print(
                f"Advertencia: {archivo.name} tiene "
                f"{df_temp.shape[1]} columnas; se esperaban "
                f"al menos {N_COLUMNAS}. Se omite."
            )
            continue

        df_temp = df_temp.iloc[:, :N_COLUMNAS].copy()
        df_temp.columns = COLUMNAS

        for col in COLUMNAS:
            df_temp[col] = pd.to_numeric(
                df_temp[col],
                errors="coerce"
            )

        df_temp["archivo_origen"] = archivo.name
        frames.append(df_temp)

    except Exception as e:
        print(f"Error al leer {archivo.name}: {e}")

if not frames:
    raise ValueError("No se pudo leer ningún archivo correctamente.")

datos = pd.concat(frames, ignore_index=True)

datos.insert(
    0,
    "id_medicion",
    np.arange(1, len(datos) + 1)
)

print(
    f"Total filas unificadas: {len(datos)} "
    f"({len(frames)} archivos procesados)"
)

datos.to_csv(
    SALIDA / "datos_unificados.csv",
    index=False
)


# ============================================================
# 2. DIAGNÓSTICO INICIAL
# ============================================================

print("\n=== 2. DIAGNÓSTICO INICIAL ===")

nulos_iniciales = int(datos[COLUMNAS].isna().sum().sum())

duplicados = int(
    datos.duplicated(subset=COLUMNAS).sum()
)

corr_temp_error = datos[
    ["temperatura", "error_distancia"]
].corr().iloc[0, 1]

print(f"Valores nulos iniciales: {nulos_iniciales}")
print(f"Mediciones duplicadas por contenido: {duplicados}")
print(
    "Correlación temperatura-error de distancia: "
    f"{corr_temp_error:.4f}"
)


# ============================================================
# 3. LIMPIEZA E IMPUTACIÓN DE COORDENADAS
# ============================================================

print("\n=== 3. LIMPIEZA E IMPUTACIÓN DE COORDENADAS ===")

limpio = datos.copy()
cambios = []

for columna in ["longitud", "latitud"]:

    original = limpio[columna].copy()

    # Los ceros se consideran coordenadas inválidas
    limpio.loc[limpio[columna] == 0, columna] = np.nan

    # Interpolación según el orden de las mediciones
    limpio[columna] = (
        limpio[columna]
        .interpolate(
            method="linear",
            limit_area="inside"
        )
        .ffill()
        .bfill()
    )

    modificados = (
        (original.isna() & limpio[columna].notna())
        |
        (original.notna() & original.ne(limpio[columna]))
    )

    for idx in limpio.index[modificados]:
        cambios.append({
            "id_medicion": limpio.loc[idx, "id_medicion"],
            "archivo_origen": limpio.loc[idx, "archivo_origen"],
            "variable": columna,
            "valor_original": original.loc[idx],
            "valor_final": limpio.loc[idx, columna],
            "tipo": "Imputación o corrección"
        })

pd.DataFrame(cambios).to_csv(
    SALIDA / "registro_correcciones_imputaciones.csv",
    index=False
)

print(f"Coordenadas imputadas/corregidas: {len(cambios)}")


# ============================================================
# 4. LIMPIEZA DEL ESPECTRO
# ============================================================

print("\n=== 4. LIMPIEZA DEL ESPECTRO ===")

espectro = limpio[COLUMNAS_ESPECTRO].copy()

# Valores infinitos se consideran inválidos
espectro = espectro.replace(
    [np.inf, -np.inf],
    np.nan
)

invalidos_espectro = int(espectro.isna().sum().sum())

print(f"Valores espectrales inválidos iniciales: {invalidos_espectro}")

# Interpolar huecos cortos dentro de cada medición
espectro = espectro.interpolate(
    axis=1,
    method="linear",
    limit=3,
    limit_area="inside"
)

faltantes_espectro = int(espectro.isna().sum().sum())

print(
    "Valores espectrales faltantes después de interpolar: "
    f"{faltantes_espectro}"
)

# No se sustituyen valores válidos por un piso artificial.
# Tampoco se reemplazan valores menores a -65 dBm.

limpio[COLUMNAS_ESPECTRO] = espectro


# ============================================================
# 5. ANÁLISIS DE FRECUENCIAS
# ============================================================

print("\n=== 5. ANÁLISIS DE FRECUENCIAS ===")

# Conversión de dBm a mW
potencia_mW = 10 ** (espectro / 10)

# Un bin está ocupado si supera -60 dBm
ocupado = espectro > UMBRAL_CONTAMINACION

# Porcentaje de mediciones en las que cada frecuencia supera -60 dBm
porcentaje_ocupacion_freq = ocupado.mean(axis=0) * 100

# Potencia promedio lineal por frecuencia, convertida a dBm
promedio_mW_freq = potencia_mW.mean(axis=0)
promedio_dBm_freq = 10 * np.log10(promedio_mW_freq)

# Frecuencia con mayor porcentaje de mediciones contaminadas
idx_mas_ocupada = int(
    np.argmax(porcentaje_ocupacion_freq.to_numpy())
)

# Frecuencia con menor porcentaje de mediciones contaminadas
idx_menos_ocupada = int(
    np.argmin(porcentaje_ocupacion_freq.to_numpy())
)

# Frecuencia con mayor potencia promedio
idx_mayor_potencia = int(
    np.argmax(promedio_dBm_freq.to_numpy())
)

print(
    f"Frecuencia con mayor ocupación: "
    f"{frecuencias[idx_mas_ocupada]:.4f} MHz "
    f"({porcentaje_ocupacion_freq.iloc[idx_mas_ocupada]:.2f}%)"
)

print(
    f"Frecuencia con menor ocupación: "
    f"{frecuencias[idx_menos_ocupada]:.4f} MHz "
    f"({porcentaje_ocupacion_freq.iloc[idx_menos_ocupada]:.2f}%)"
)

print(
    f"Frecuencia con mayor potencia promedio: "
    f"{frecuencias[idx_mayor_potencia]:.4f} MHz "
    f"({promedio_dBm_freq.iloc[idx_mayor_potencia]:.2f} dBm)"
)

tabla_frecuencias = pd.DataFrame({
    "frecuencia_MHz": frecuencias,
    "ocupacion_porcentaje": porcentaje_ocupacion_freq.to_numpy(),
    "potencia_promedio_dBm": promedio_dBm_freq.to_numpy()
})

tabla_frecuencias.to_csv(
    SALIDA / "analisis_frecuencias.csv",
    index=False
)


# ============================================================
# 6. ANÁLISIS DE LOS CUATRO CANALES
# ============================================================

print("\n=== 6. ANÁLISIS DE CANALES ===")

canales = {
    "Canal_A": (840, 845),
    "Canal_B": (845, 850),
    "Canal_C": (850, 855),
    "Canal_D": (855, 860)
}

resultados_canales = []

for nombre, (f_inicio, f_fin) in canales.items():

    # Evitar contar dos veces los límites entre canales
    if nombre == "Canal_D":
        mascara = (
            (frecuencias >= f_inicio)
            & (frecuencias <= f_fin)
        )
    else:
        mascara = (
            (frecuencias >= f_inicio)
            & (frecuencias < f_fin)
        )

    espectro_canal = espectro.loc[:, mascara]
    potencia_canal = potencia_mW.loc[:, mascara]

    ocupado_canal = espectro_canal > UMBRAL_CONTAMINACION

    # Porcentaje de bins del canal que superan -60 dBm
    pct_bins = ocupado_canal.to_numpy().mean() * 100

    # Porcentaje de mediciones con al menos un bin contaminado
    pct_mediciones = ocupado_canal.any(axis=1).mean() * 100

    # Potencia promedio del canal en escala lineal
    potencia_media_mW = potencia_canal.mean(axis=1)
    potencia_media_dBm = 10 * np.log10(potencia_media_mW)

    resultados_canales.append({
        "canal": nombre,
        "frecuencia_inicio_MHz": f_inicio,
        "frecuencia_fin_MHz": f_fin,
        "ocupacion_bins_porcentaje": pct_bins,
        "mediciones_con_contaminacion_porcentaje": pct_mediciones,
        "potencia_media_dBm": potencia_media_dBm.mean(),
        "potencia_maxima_dBm": espectro_canal.max().max()
    })

    print(
        f"{nombre}: {pct_bins:.2f}% de bins contaminados; "
        f"{pct_mediciones:.2f}% de mediciones con contaminación"
    )

tabla_canales = pd.DataFrame(resultados_canales)

tabla_canales.to_csv(
    SALIDA / "resultados_canales.csv",
    index=False
)

canal_mas = tabla_canales.loc[
    tabla_canales["ocupacion_bins_porcentaje"].idxmax()
]

canal_menos = tabla_canales.loc[
    tabla_canales["ocupacion_bins_porcentaje"].idxmin()
]

print(
    f"\nCanal con mayor ocupación: {canal_mas['canal']} "
    f"({canal_mas['ocupacion_bins_porcentaje']:.2f}%)"
)

print(
    f"Canal con menor ocupación: {canal_menos['canal']} "
    f"({canal_menos['ocupacion_bins_porcentaje']:.2f}%)"
)


# ============================================================
# 7. TEMPERATURA Y CONTAMINACIÓN
# ============================================================

print("\n=== 7. TEMPERATURA VS CONTAMINACIÓN ===")

limpio["porcentaje_bins_contaminados"] = (
    ocupado.mean(axis=1).to_numpy() * 100
)

corr_temp_contaminacion = limpio[
    ["temperatura", "porcentaje_bins_contaminados"]
].corr().iloc[0, 1]

print(
    "Correlación temperatura-contaminación: "
    f"{corr_temp_contaminacion:.4f}"
)


# ============================================================
# 8. PREPARACIÓN DEL DATASET PARA DASHBOARD
# ============================================================

print("\n=== 8. PREPARANDO DATASET PARA DASHBOARD ===")

# Potencia en las frecuencias con mayor y menor ocupación
limpio["pot_freq_mas_ocupada"] = (
    espectro.iloc[:, idx_mas_ocupada]
)

limpio["pot_freq_menos_ocupada"] = (
    espectro.iloc[:, idx_menos_ocupada]
)

# Porcentaje de bins contaminados por medición
# Útil para visualizar contaminación junto a latitud y longitud.

limpio.to_csv(
    SALIDA / "dataset_final_procesado.csv",
    index=False
)


# ============================================================
# 9. RESUMEN GENERAL
# ============================================================

print("\n=== 9. GUARDANDO RESUMEN ===")

resumen = pd.DataFrame({
    "indicador": [
        "mediciones",
        "archivos_procesados",
        "nulos_iniciales",
        "duplicados_detectados",
        "valores_espectrales_invalidos_iniciales",
        "faltantes_espectrales_despues_de_interpolar",
        "coordenadas_imputadas_o_corregidas",
        "correlacion_temperatura_error_distancia",
        "correlacion_temperatura_contaminacion",
        "frecuencia_mayor_ocupacion_MHz",
        "frecuencia_menor_ocupacion_MHz",
        "frecuencia_mayor_potencia_promedio_MHz",
        "canal_mayor_ocupacion",
        "canal_menor_ocupacion"
    ],
    "valor": [
        len(limpio),
        len(frames),
        nulos_iniciales,
        duplicados,
        invalidos_espectro,
        faltantes_espectro,
        len(cambios),
        corr_temp_error,
        corr_temp_contaminacion,
        frecuencias[idx_mas_ocupada],
        frecuencias[idx_menos_ocupada],
        frecuencias[idx_mayor_potencia],
        canal_mas["canal"],
        canal_menos["canal"]
    ]
})

resumen.to_csv(
    SALIDA / "resumen_analisis.csv",
    index=False
)