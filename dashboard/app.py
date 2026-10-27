"""
Dashboard interactivo — Índices de Provisiones por Riesgo de Crédito
Sistema Bancario Chileno | CMF | 2016–2026
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

# ── Configuración de la página ──────────────────────────────────────────────
st.set_page_config(
    page_title="Riesgo de Crédito — Banca Chilena",
    page_icon="🏦",
    layout="wide",
)

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"

TIPOS = {
    "Comercial": "indice_comercial",
    "Consumo":   "indice_consumo",
    "Vivienda":  "indice_vivienda",
}

COVID_START = "2020-03-01"
COVID_END   = "2021-06-01"


# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos():
    df_prov = pd.read_csv(DATA_DIR / "provisiones_por_tipo.csv", parse_dates=["fecha"])
    df_cart = pd.read_csv(DATA_DIR / "calidad_cartera.csv",      parse_dates=["fecha"])
    df_sis  = pd.read_csv(DATA_DIR / "provisiones_por_tipo_sistema.csv", parse_dates=["fecha"])
    return df_prov, df_cart, df_sis


df_prov, df_cart, df_sis = cargar_datos()

# Bancos con al menos 60 meses de datos para no mostrar instituciones fugaces
bancos_validos = (
    df_prov.groupby("banco")["fecha"].count()
    [lambda s: s >= 60]
    .index.tolist()
)
bancos_validos.sort()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Filtros")

    bancos_sel = st.multiselect(
        "Bancos",
        options=bancos_validos,
        default=["Banco de Chile", "Banco del Estado de Chile",
                 "Banco Santander-Chile", "Banco de Crédito e Inversiones"],
    )

    anio_min, anio_max = st.slider(
        "Rango de años",
        min_value=2016, max_value=2026,
        value=(2016, 2026),
    )

    tipo_sel = st.selectbox("Tipo de crédito", list(TIPOS.keys()), index=1)
    col_sel  = TIPOS[tipo_sel]

    mostrar_covid = st.toggle("Marcar período COVID", value=True)

    st.divider()
    st.caption("Fuente: CMF — Indicadores de Provisiones por Riesgo de Crédito de Bancos")


# ── Filtrado base ─────────────────────────────────────────────────────────────
df_filtrado = df_prov[
    df_prov["banco"].isin(bancos_sel) &
    (df_prov["fecha"].dt.year >= anio_min) &
    (df_prov["fecha"].dt.year <= anio_max)
].copy()


def agregar_covid(fig):
    """Agrega una banda sombreada para el período COVID si el toggle está activo."""
    if mostrar_covid:
        fig.add_vrect(
            x0=COVID_START, x1=COVID_END,
            fillcolor="red", opacity=0.08,
            layer="below", line_width=0,
            annotation_text="COVID", annotation_position="top left",
        )
    return fig


# ── Header ───────────────────────────────────────────────────────────────────
st.title("Riesgo de Crédito — Sistema Bancario Chileno")
st.markdown("Análisis de índices de provisiones por riesgo de crédito · CMF · 2016–2026")
st.divider()


# ── KPIs ─────────────────────────────────────────────────────────────────────
if bancos_sel and not df_filtrado.empty:
    ult_fecha = df_filtrado["fecha"].max()
    df_ult    = df_filtrado[df_filtrado["fecha"] == ult_fecha]

    st.subheader(f"Último dato disponible — {ult_fecha.strftime('%B %Y')}")
    cols = st.columns(len(bancos_sel))

    for col, banco in zip(cols, bancos_sel):
        fila = df_ult[df_ult["banco"] == banco]
        if not fila.empty:
            val = fila[col_sel].values[0]
            col.metric(label=banco, value=f"{val:.2f}%" if pd.notna(val) else "N/D")

    st.divider()


# ── Vista 1: Evolución del sistema ───────────────────────────────────────────
st.subheader("Evolución del sistema bancario")
st.caption("Índice oficial del sistema publicado por la CMF: provisiones totales sobre colocaciones totales.")

df_sistema = df_sis[
    (df_sis["fecha"].dt.year >= anio_min) &
    (df_sis["fecha"].dt.year <= anio_max)
]

fig_sistema = go.Figure()
colores = ["#1f77b4", "#ff7f0e", "#2ca02c"]
for (nombre, col), color in zip(TIPOS.items(), colores):
    fig_sistema.add_trace(go.Scatter(
        x=df_sistema["fecha"], y=df_sistema[col],
        name=nombre, line=dict(color=color, width=2),
    ))

fig_sistema = agregar_covid(fig_sistema)
fig_sistema.update_layout(
    xaxis_title="Fecha", yaxis_title="Índice de provisiones (%)",
    legend_title="Tipo de crédito", hovermode="x unified",
    height=380,
)
st.plotly_chart(fig_sistema, use_container_width=True)


# ── Vista 2: Comparativa por banco ───────────────────────────────────────────
st.subheader(f"Comparativa por banco — Crédito {tipo_sel}")

if bancos_sel and not df_filtrado.empty:
    df_lineas = df_filtrado[["fecha", "banco", col_sel]].dropna()
    fig_bancos = px.line(
        df_lineas, x="fecha", y=col_sel, color="banco",
        labels={"fecha": "Fecha", col_sel: "Índice (%)", "banco": "Banco"},
        height=400,
    )
    fig_bancos = agregar_covid(fig_bancos)
    fig_bancos.update_layout(hovermode="x unified", legend_title="Banco")
    st.plotly_chart(fig_bancos, use_container_width=True)
else:
    st.info("Selecciona al menos un banco en el panel izquierdo.")


# ── Vista 3: Heatmap ─────────────────────────────────────────────────────────
st.subheader(f"Heatmap — Índice {tipo_sel} promedio anual por banco")

if bancos_sel:
    df_heat = df_prov[
        df_prov["banco"].isin(bancos_sel) &
        (df_prov["fecha"].dt.year >= anio_min) &
        (df_prov["fecha"].dt.year <= anio_max)
    ].copy()
    df_heat["anio"] = df_heat["fecha"].dt.year

    pivot = (
        df_heat.groupby(["banco", "anio"])[col_sel]
        .mean()
        .unstack()
        .round(2)
    )

    fig_heat = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        labels={"x": "Año", "y": "Banco", "color": "Índice (%)"},
        text_auto=".1f",
        aspect="auto",
        height=max(300, len(bancos_sel) * 50),
    )
    fig_heat.update_layout(coloraxis_colorbar_title="Índice (%)")
    st.plotly_chart(fig_heat, use_container_width=True)


# ── Vista 4: Ranking ─────────────────────────────────────────────────────────
st.subheader(f"Ranking de bancos por índice {tipo_sel} promedio")

df_ranking = (
    df_prov[
        df_prov["banco"].isin(bancos_validos) &
        (df_prov["fecha"].dt.year >= anio_min) &
        (df_prov["fecha"].dt.year <= anio_max)
    ]
    .groupby("banco")[col_sel]
    .mean()
    .dropna()
    .sort_values(ascending=False)
    .reset_index()
    .rename(columns={"banco": "Banco", col_sel: f"Índice {tipo_sel} promedio (%)"})
    .round(2)
)
df_ranking.index += 1

fig_ranking = px.bar(
    df_ranking, x=f"Índice {tipo_sel} promedio (%)", y="Banco",
    orientation="h",
    color=f"Índice {tipo_sel} promedio (%)",
    color_continuous_scale="YlOrRd",
    height=max(350, len(df_ranking) * 35),
    labels={"Banco": ""},
)
fig_ranking.update_layout(
    yaxis=dict(autorange="reversed"),
    coloraxis_showscale=False,
)
st.plotly_chart(fig_ranking, use_container_width=True)

st.divider()

# ── Conclusiones ─────────────────────────────────────────────────────────────
st.subheader("Conclusiones del análisis")

col1, col2 = st.columns(2)

with col1:
    st.info(
        "**COVID: alza inicial y luego caída**  \n"
        "El índice de consumo del sistema pasó de 6.22% (pre-pandemia) a un peak de 7.02% a mediados de 2020, "
        "y cayó a 5.70% en septiembre–octubre 2021, en coincidencia con los retiros de fondos de pensiones "
        "y las ayudas estatales."
    )
    st.info(
        "**Post-pandemia el riesgo superó los niveles previos**  \n"
        "Desde 2022 el índice de consumo promedia 7.47%. 2025 cerró con 7.92%, el promedio anual "
        "más alto del período (peak de 8.19% en febrero 2025)."
    )
    st.info(
        "**BancoEstado lidera el riesgo de consumo**  \n"
        "Con un índice promedio de 10.53%, seguido por Banco Ripley (9.22%) y Banco Falabella (7.54%)."
    )

with col2:
    st.success(
        "**Banco de Chile tiene la cartera de consumo más estable**  \n"
        "Su índice se movió en un rango de 2.2 puntos (5.42%–7.62%), el menor entre los bancos "
        "con historia completa. Le sigue Santander (2.6 puntos)."
    )
    st.success(
        "**El crédito hipotecario es el más seguro**  \n"
        "El índice de vivienda está bajo consumo y comercial en el 100% de los meses y bancos. "
        "En el sistema bajó de 0.94% (2016) a 0.62% (2026)."
    )
    st.success(
        "**Divergencia reciente entre bancos**  \n"
        "Banco Falabella bajó de 10.72% (dic. 2023) a 6.73% (mar. 2026) y BancoEstado de 13.77% "
        "(nov. 2024) a 11.64%, mientras Banco de Chile subió de 6.44% (2022) a 7.36% (2026)."
    )

st.divider()
st.caption(
    "Desarrollado por **Marcelo Adolfo Corro Troncoso** · "
    "Datos: CMF Chile · Indicadores de Provisiones por Riesgo de Crédito  \n"
    "*Este análisis es de carácter académico y fue desarrollado con fines de portafolio profesional. "
    "No constituye asesoría financiera ni representa la opinión de ninguna institución. "
    "Los datos utilizados son de acceso público y provienen de la CMF Chile.*"
)
