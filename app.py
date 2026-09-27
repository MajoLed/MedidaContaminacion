# -*- coding: utf-8 -*-
"""
Dashboard interactivo — ocupación de espectro 840-860 MHz (Medellín)

Lee 'resultados/dataset_final_procesado.csv' (generado por el script de
análisis) y muestra:
  - Ubicación de las mediciones
  - Ruta de la estación móvil
  - Mapa de calor por canal (A, B, C, D)
  - Mapa de calor de temperatura
  - Mapa de calor de la frecuencia más contaminada

Ejecutar:
    pip install streamlit plotly pandas numpy
    streamlit run dashboard_espectro.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------
# CONFIGURACIÓN (debe coincidir con el script de análisis)
# ------------------------------------------------------------------
RUTA_CSV = "resultados/dataset_final_procesado.csv"
N_ESPECTRO = 1024
F_MIN, F_MAX = 840.0, 860.0
UMBRAL_CONTAMINACION = -60.0
CANALES = {
    "Canal A (840-845 MHz)": (840, 845),
    "Canal B (845-850 MHz)": (845, 850),
    "Canal C (850-855 MHz)": (850, 855),
    "Canal D (855-860 MHz)": (855, 860),
}
COLUMNAS_ESPECTRO = [f"espectro_{i+1}" for i in range(N_ESPECTRO)]
FRECUENCIAS = np.linspace(F_MIN, F_MAX, N_ESPECTRO)

st.set_page_config(page_title="Dashboard iterativo - Contaminacion Espectro", layout="wide")

# Compatibilidad entre versiones de Plotly: las versiones nuevas (>=6) renombraron
# scatter_mapbox/density_mapbox/Scattermapbox a scatter_map/density_map/Scattermap.
scatter_map_fn = getattr(px, "scatter_map", None) or px.scatter_mapbox
density_map_fn = getattr(px, "density_map", None) or px.density_mapbox
Scattermap = getattr(go, "Scattermap", None) or go.Scattermapbox
USANDO_MAP_NUEVO = hasattr(px, "scatter_map")
CLAVE_ESTILO = "map_style" if USANDO_MAP_NUEVO else "mapbox_style"
CLAVE_CENTRO = "map_center" if USANDO_MAP_NUEVO else "mapbox_center"
CLAVE_ZOOM = "map_zoom" if USANDO_MAP_NUEVO else "mapbox_zoom"


# ------------------------------------------------------------------
# CARGA Y PREPARACIÓN DE DATOS
# ------------------------------------------------------------------
@st.cache_data
def cargar_datos(ruta):
    df = pd.read_csv(ruta)
    faltantes = [c for c in COLUMNAS_ESPECTRO + ["latitud", "longitud", "temperatura", "id_medicion"] if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en el CSV: {faltantes}")

    espectro = df[COLUMNAS_ESPECTRO].to_numpy(dtype=float)

    # potencia máxima y % de bins contaminados por canal, para cada medición
    columnas_nuevas = {}
    for nombre, (a, b) in CANALES.items():
        if nombre.startswith("Canal D"):
            m = (FRECUENCIAS >= a) & (FRECUENCIAS <= b)
        else:
            m = (FRECUENCIAS >= a) & (FRECUENCIAS < b)
        sub = espectro[:, m]
        columnas_nuevas[f"{nombre}__max_dBm"] = np.nanmax(sub, axis=1)
        columnas_nuevas[f"{nombre}__pct_contaminado"] = (np.nan_to_num(sub) > UMBRAL_CONTAMINACION).mean(axis=1) * 100

    # frecuencia globalmente más contaminada (para su propio mapa de calor)
    ocupado = espectro > UMBRAL_CONTAMINACION
    pct_por_freq = np.nanmean(ocupado, axis=0) * 100
    idx_peor = int(np.nanargmax(pct_por_freq))
    columnas_nuevas["potencia_freq_mas_contaminada"] = espectro[:, idx_peor]
    freq_peor = FRECUENCIAS[idx_peor]

    df = pd.concat([df, pd.DataFrame(columnas_nuevas, index=df.index)], axis=1)
    df = df.sort_values("id_medicion").reset_index(drop=True)
    return df, freq_peor, pct_por_freq


try:
    datos, freq_mas_contaminada, pct_por_freq = cargar_datos(RUTA_CSV)
except FileNotFoundError:
    st.error(f"No encontré '{RUTA_CSV}'. Corre primero el script de análisis para generarlo.")
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

centro = dict(lat=datos["latitud"].mean(), lon=datos["longitud"].mean())


# ------------------------------------------------------------------
# ESTIMACIÓN DE LA FUENTE POR BANDA (bonificación) — superficie de tendencia
# ------------------------------------------------------------------
def latlon_a_metros(lat, lon, lat0, lon0):
    """Proyección equirectangular local (válida a la escala de una ciudad)."""
    R = 6371000.0
    x = np.radians(lon - lon0) * R * np.cos(np.radians(lat0))
    y = np.radians(lat - lat0) * R
    return x, y


def metros_a_latlon(x, y, lat0, lon0):
    R = 6371000.0
    lat = lat0 + np.degrees(y / R)
    lon = lon0 + np.degrees(x / (R * np.cos(np.radians(lat0))))
    return lat, lon


@st.cache_data
def estimar_fuentes_por_canal(df, canales, lat0, lon0):
    """
    Para cada canal, ajusta una superficie cuadrática (paraboloide) a la
    potencia medida en función de la posición (x, y en metros):

        P(x, y) = a + b1*x + b2*y + b3*x^2 + b4*y^2 + b5*x*y

    El vértice de ese paraboloide es la posición que EXTRAPOLA la tendencia
    de la potencia más allá de los puntos muestreados: es la estimación de
    dónde estaría la fuente si la señal sigue decayendo con la distancia de
    la misma forma en que lo hace sobre la ruta medida.

    Si el ajuste no tiene un máximo bien definido (superficie sin curvatura
    suficiente / silla), se usa como respaldo el centroide ponderado por
    potencia lineal (mW) de los puntos más fuertes.
    """
    x, y = latlon_a_metros(df["latitud"].to_numpy(), df["longitud"].to_numpy(), lat0, lon0)
    x_min, x_max, y_min, y_max = x.min(), x.max(), y.min(), y.max()

    filas = []
    for nombre in canales:
        p = df[f"{nombre}__max_dBm"].to_numpy()
        valido = np.isfinite(p)
        xs, ys, ps = x[valido], y[valido], p[valido]

        A = np.column_stack([np.ones_like(xs), xs, ys, xs**2, ys**2, xs * ys])
        coef, *_ = np.linalg.lstsq(A, ps, rcond=None)
        a0, b1, b2, b3, b4, b5 = coef
        H = np.array([[2 * b3, b5], [b5, 2 * b4]])
        det = np.linalg.det(H)

        if det > 0 and b3 < 0:
            xe, ye = np.linalg.solve(H, [-b1, -b2])
            metodo = "Superficie cuadrática (extrapolación)"
        else:
            w = 10 ** (ps / 10.0)          # potencia lineal (mW) como peso
            xe, ye = np.average(xs, weights=w), np.average(ys, weights=w)
            metodo = "Centroide ponderado (respaldo, sin vértice cuadrático válido)"

        lat_e, lon_e = metros_a_latlon(xe, ye, lat0, lon0)
        fuera = not (x_min <= xe <= x_max and y_min <= ye <= y_max)
        idx_max = int(np.nanargmax(p))
        filas.append({
            "canal": nombre,
            "lat_estimada": lat_e, "lon_estimada": lon_e,
            "metodo": metodo,
            "fuera_del_area_muestreada": fuera,
            "potencia_max_observada_dBm": float(p[idx_max]),
            "lat_max_observada": float(df["latitud"].iloc[idx_max]),
            "lon_max_observada": float(df["longitud"].iloc[idx_max]),
        })
    return pd.DataFrame(filas).set_index("canal")


fuentes = estimar_fuentes_por_canal(datos, list(CANALES.keys()), centro["lat"], centro["lon"])


# ------------------------------------------------------------------
# BARRA LATERAL
# ------------------------------------------------------------------
st.sidebar.title("Filtros")
canal_sel = st.sidebar.selectbox("Canal para el mapa de calor", list(CANALES.keys()))
mostrar_valor = st.sidebar.radio("Métrica del canal", ["Potencia máxima (dBm)", "% de bins contaminados"])
mapbox_style = st.sidebar.selectbox("Estilo de mapa", ["open-street-map", "carto-positron", "carto-darkmatter"])

st.title("Ocupación de espectro 840-860 MHz — Medellín")

st.caption(
    f"Hecho por: Majo L - ID: 00559241\n"
    f"frecuencia más contaminada del sistema: {freq_mas_contaminada:.2f} MHz"
)


# ------------------------------------------------------------------
# 1) UBICACIÓN DE LAS MEDICIONES + 2) RUTA
# ------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Ubicación de las mediciones")
    fig = scatter_map_fn(
        datos, lat="latitud", lon="longitud",
        hover_data=["id_medicion", "temperatura"],
        zoom=13, height=480,
    )
    fig.update_traces(marker=dict(size=7, color="#1f77b4"))
    fig.update_layout(**{CLAVE_ESTILO: mapbox_style, CLAVE_CENTRO: centro}, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Ruta de la estación móvil")
    ruta = datos.sort_values("id_medicion")
    fig = go.Figure()
    fig.add_trace(Scattermap(
        lat=ruta["latitud"], lon=ruta["longitud"], mode="lines+markers",
        marker=dict(size=4, color="#1f77b4"), line=dict(width=3, color="#1f77b4"), name="Ruta",
    ))
    fig.add_trace(Scattermap(
        lat=[ruta["latitud"].iloc[0]], lon=[ruta["longitud"].iloc[0]],
        mode="markers", marker=dict(size=13, color="green"), name="Inicio",
    ))
    fig.add_trace(Scattermap(
        lat=[ruta["latitud"].iloc[-1]], lon=[ruta["longitud"].iloc[-1]],
        mode="markers", marker=dict(size=13, color="red"), name="Fin",
    ))
    fig.update_layout(
        **{CLAVE_ESTILO: mapbox_style, CLAVE_CENTRO: centro, CLAVE_ZOOM: 13},
        height=480, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# 3) MAPA DE CALOR POR CANAL (A, B, C, D)
# ------------------------------------------------------------------
st.subheader(f"Mapa de calor — {canal_sel}")
col_valor = f"{canal_sel}__max_dBm" if mostrar_valor.startswith("Potencia") else f"{canal_sel}__pct_contaminado"
fig = density_map_fn(
    datos, lat="latitud", lon="longitud", z=col_valor,
    radius=18, zoom=13, center=centro, height=520,
    color_continuous_scale="Inferno",
    labels={col_valor: mostrar_valor},
)
fig.update_layout(**{CLAVE_ESTILO: mapbox_style}, margin=dict(l=0, r=0, t=0, b=0))
fig.add_trace(Scattermap(
    lat=[fuentes.loc[canal_sel, "lat_estimada"]], lon=[fuentes.loc[canal_sel, "lon_estimada"]],
    mode="markers+text", marker=dict(size=18, color="cyan", symbol="star"),
    text=["Fuente estimada"], textposition="top center", name="Fuente estimada",
))
st.plotly_chart(fig, use_container_width=True)
st.caption(
    f"Fuente estimada del {canal_sel.split(' (')[0]}: "
    f"lat {fuentes.loc[canal_sel, 'lat_estimada']:.5f}, lon {fuentes.loc[canal_sel, 'lon_estimada']:.5f} · "
    f"método: {fuentes.loc[canal_sel, 'metodo']}"
    + (" · **fuera del área muestreada (extrapolación)**" if fuentes.loc[canal_sel, "fuera_del_area_muestreada"] else " · dentro del área muestreada")
)

c1, c2, c3, c4 = st.columns(4)
for c, (nombre, _) in zip([c1, c2, c3, c4], CANALES.items()):
    c.metric(nombre.split(" (")[0], f"{datos[f'{nombre}__pct_contaminado'].mean():.1f}% cont.")


# ------------------------------------------------------------------
# 4) MAPA DE CALOR DE TEMPERATURA  /  5) FRECUENCIA MÁS CONTAMINADA
# ------------------------------------------------------------------
col3, col4 = st.columns(2)

with col3:
    st.subheader("Mapa de calor — Temperatura del sensor")
    fig = density_map_fn(
        datos, lat="latitud", lon="longitud", z="temperatura",
        radius=18, zoom=13, center=centro, height=480,
        color_continuous_scale="RdBu_r",
    )
    fig.update_layout(**{CLAVE_ESTILO: mapbox_style}, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader(f"Mapa de calor — Frecuencia más contaminada ({freq_mas_contaminada:.2f} MHz)")
    fig = density_map_fn(
        datos, lat="latitud", lon="longitud", z="potencia_freq_mas_contaminada",
        radius=18, zoom=13, center=centro, height=480,
        color_continuous_scale="Inferno",
        labels={"potencia_freq_mas_contaminada": "dBm"},
    )
    fig.update_layout(**{CLAVE_ESTILO: mapbox_style}, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# ESTIMACIÓN DE LA FUENTE DE CONTAMINACIÓN POR BANDA (bonificación)
# ------------------------------------------------------------------
st.subheader("Bonificación — Estimación de la fuente de contaminación por banda")
st.caption(
    "Para cada canal se ajusta una superficie cuadrática a la potencia medida en función de la "
    "posición; el vértice de esa superficie extrapola hacia dónde apunta la tendencia de la señal, "
    "incluso fuera de la ruta recorrida. El punto de mayor potencia realmente observado se muestra "
    "como referencia."
)

colores_canal = {"Canal A (840-845 MHz)": "#4c78a8", "Canal B (845-850 MHz)": "#f58518",
                  "Canal C (850-855 MHz)": "#54a24b", "Canal D (855-860 MHz)": "#b279a2"}

fig = go.Figure()
fig.add_trace(Scattermap(
    lat=datos["latitud"], lon=datos["longitud"], mode="lines",
    line=dict(width=1, color="lightgray"), name="Ruta medida", hoverinfo="skip",
))
for nombre, fila in fuentes.iterrows():
    color = colores_canal.get(nombre, "cyan")
    fig.add_trace(Scattermap(
        lat=[fila["lat_max_observada"]], lon=[fila["lon_max_observada"]],
        mode="markers", marker=dict(size=9, color=color, opacity=0.5),
        name=f"{nombre.split(' (')[0]} — máx. observado",
    ))
    fig.add_trace(Scattermap(
        lat=[fila["lat_estimada"]], lon=[fila["lon_estimada"]],
        mode="markers+text", marker=dict(size=17, color=color, symbol="star"),
        text=[nombre.split(" (")[0]], textposition="top center",
        name=f"{nombre.split(' (')[0]} — fuente estimada",
    ))
fig.update_layout(
    **{CLAVE_ESTILO: mapbox_style, CLAVE_CENTRO: centro, CLAVE_ZOOM: 12.5},
    height=560, margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
)
st.plotly_chart(fig, use_container_width=True)

tabla_fuentes = fuentes[["lat_estimada", "lon_estimada", "metodo", "fuera_del_area_muestreada", "potencia_max_observada_dBm"]].copy()
tabla_fuentes.columns = ["Latitud estimada", "Longitud estimada", "Método", "Fuera del área muestreada", "Potencia máx. observada (dBm)"]
st.dataframe(tabla_fuentes.round(5), use_container_width=True)


# ------------------------------------------------------------------
# GRÁFICA DE OCUPACIÓN POR FRECUENCIA (contexto de todo el sistema)
# ------------------------------------------------------------------
st.subheader("Ocupación por frecuencia en todo el sistema")
fig = go.Figure()
fig.add_trace(go.Scatter(x=FRECUENCIAS, y=pct_por_freq, mode="lines", name="% mediciones contaminadas"))
colores = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]
for (nombre, (a, b)), color in zip(CANALES.items(), colores):
    fig.add_vrect(x0=a, x1=b, fillcolor=color, opacity=0.10, line_width=0,
                  annotation_text=nombre.split(" ")[1], annotation_position="top left")
fig.update_layout(xaxis_title="Frecuencia (MHz)", yaxis_title="% de mediciones > umbral", height=380)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Ver datos crudos filtrados"):
    st.dataframe(datos.drop(columns=COLUMNAS_ESPECTRO), use_container_width=True)