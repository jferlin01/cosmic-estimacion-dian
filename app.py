"""
Calculadora de Estimación COSMIC — Interventoría DIAN
Basada en la Metodología de Estimación de Esfuerzo (ISO/IEC 19761)

Módulos:
  1. COSMIC CFP  — Conteo de movimientos de datos → CFP → Horas
  2. PERT        — Estimación tres puntos (O, M, P)
  3. Complejidad — Componentes no funcionales
  4. SDLC        — Distribución de esfuerzo por fases
  5. Comparación — Contratista vs. Interventoría (regla 10 %)
  6. Historial   — Registro acumulado de estimaciones
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Calculadora COSMIC — Interventoría DIAN",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constantes de la metodología
# ---------------------------------------------------------------------------
TASA_H_CFP_MIN  = 8.0
TASA_H_CFP_MED  = 10.2
TASA_H_CFP_MAX  = 12.0

FACTORES_AJUSTE = {
    "Novedad tecnológica (IA, cloud nativa)":       {"min": 1.0, "ref": 1.2, "max": 1.5},
    "Integración con sistemas legados DIAN":        {"min": 1.0, "ref": 1.15,"max": 1.3},
    "Requisitos de seguridad (SGSI DIAN)":          {"min": 1.0, "ref": 1.1, "max": 1.25},
    "Estabilidad de requerimientos":                {"min": 0.9, "ref": 1.0, "max": 1.2},
    "Curva de aprendizaje del equipo":              {"min": 0.9, "ref": 1.0, "max": 1.3},
}

DIST_SDLC = {
    "Pre-análisis y estimación":      {"Baja": 5,  "Media": 5,  "Alta": 5},
    "Análisis y Diseño técnico":      {"Baja": 15, "Media": 18, "Alta": 20},
    "Construcción (Desarrollo)":      {"Baja": 40, "Media": 38, "Alta": 35},
    "Pruebas (unit, integr., seg.)":  {"Baja": 25, "Media": 25, "Alta": 25},
    "Transición y liberación":        {"Baja": 8,  "Media": 8,  "Alta": 8},
    "Estabilización":                 {"Baja": 4,  "Media": 4,  "Alta": 5},
    "Transferencia de conocimiento":  {"Baja": 3,  "Media": 2,  "Alta": 2},
}

COMP_RANGOS = {
    "Baja":  (8,   40,  "CRUD básico, endpoint REST simple"),
    "Media": (40,  120, "Integración con ESB, módulo de reglas fiscales"),
    "Alta":  (120, 400, "Motor de riesgo tributario, integración multinube"),
}

TIPO_MOVIMIENTO_COLOR = {"E": "#0070F2", "X": "#307B47", "R": "#E6A117", "W": "#BB0000"}
TIPO_MOVIMIENTO_DESC  = {
    "E": "Entrada — datos del usuario funcional hacia el proceso",
    "X": "Salida  — datos del proceso hacia el usuario funcional",
    "R": "Lectura — datos del almacenamiento persistente al proceso",
    "W": "Escritura — datos del proceso al almacenamiento persistente",
}

# ---------------------------------------------------------------------------
# Persistencia del historial — session_state (compatible con nube)
# ---------------------------------------------------------------------------
def _load_hist() -> list[dict]:
    return st.session_state.get("historial", [])

def _save_hist(records: list[dict]) -> None:
    st.session_state["historial"] = records

def _append_hist(entry: dict) -> None:
    records = _load_hist()
    entry["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    records.append(entry)
    _save_hist(records)

# ---------------------------------------------------------------------------
# Helpers de cálculo
# ---------------------------------------------------------------------------
def _pert(o: float, m: float, p: float) -> tuple[float, float]:
    """Retorna (E, sigma) de PERT."""
    e = (o + 4 * m + p) / 6
    sigma = (p - o) / 6
    return e, sigma

def _desviacion(est_cont: float, est_int: float) -> float:
    if est_int == 0:
        return 0.0
    return ((est_cont - est_int) / est_int) * 100

def _decision(desv: float) -> tuple[str, str, float]:
    """Retorna (etiqueta, color_hex, horas_acordadas)."""
    # se llama con est_cont y est_int ya conocidos
    pass  # se implementa inline en el módulo

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #001F5B !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .metric-card {
        background: #F0F4FF; border-radius: 8px;
        padding: 14px 18px; margin-bottom: 8px;
        border-left: 4px solid #0070F2;
    }
    .cfp-badge {
        display: inline-block; background: #0070F2; color: white;
        border-radius: 20px; padding: 3px 12px; font-weight: bold;
        font-size: 1.1em; margin-left: 8px;
    }
    .decision-aprobada  { background: #d4edda; color: #155724; padding: 10px 16px; border-radius: 6px; font-weight: bold; }
    .decision-promedio  { background: #fff3cd; color: #856404; padding: 10px 16px; border-radius: 6px; font-weight: bold; }
    .decision-rechazada { background: #f8d7da; color: #721c24; padding: 10px 16px; border-radius: 6px; font-weight: bold; }
    h2 { color: #001F5B; }
    h3 { color: #0070F2; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — navegación
# ---------------------------------------------------------------------------
LOGO_PATH = Path(__file__).parent / "Dian_Logo.png"

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("## Calculadora COSMIC")
    st.markdown("*Interventoría DIAN — PAMD 33-LPI-S-24*")
    st.divider()
    modulo = st.radio(
        "Módulo",
        [
            "📏 COSMIC CFP",
            "📊 PERT (Tres Puntos)",
            "🔧 Complejidad de Componentes",
            "📋 Distribución SDLC",
            "⚖️ Comparación Contratista",
            "📁 Historial",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("ISO/IEC 19761 · ISBSG 2024 · COCOMO II · PMBOK 7ª ed.")

# ===========================================================================
# MÓDULO 1 — COSMIC CFP
# ===========================================================================
if modulo == "📏 COSMIC CFP":
    st.header("📏 Módulo COSMIC — Conteo de Puntos Función")
    st.caption(
        "ISO/IEC 19761 · Cada movimiento de datos = 1 CFP · "
        "Tipos: **E** Entrada · **X** Salida · **R** Lectura · **W** Escritura"
    )

    # ── Leyenda de tipos ───────────────────────────────────────────────────
    with st.expander("📖 Referencia rápida de tipos de movimiento", expanded=False):
        cols = st.columns(4)
        for col, (tipo, desc) in zip(cols, TIPO_MOVIMIENTO_DESC.items()):
            col.markdown(
                f"<div style='border-left:4px solid {TIPO_MOVIMIENTO_COLOR[tipo]};"
                f"padding:6px 10px;border-radius:4px;background:#f8f9fa'>"
                f"<b style='color:{TIPO_MOVIMIENTO_COLOR[tipo]};font-size:1.3em'>{tipo}</b><br>"
                f"<small>{desc}</small></div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Metadatos de la solicitud ──────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        id_solicitud = st.text_input("ID Solicitud de servicio", placeholder="SS-2025-001")
    with c2:
        nombre_fur   = st.text_input("Nombre del sistema / módulo", placeholder="Sistema académico / módulo docentes")
    with c3:
        tasa_sel     = st.selectbox(
            "Tasa de productividad (h/CFP)",
            ["8,0 h/CFP — Percentil 25 ISBSG",
             "10,2 h/CFP — Mediana ISBSG",
             "12,0 h/CFP — Percentil 75 ISBSG",
             "Personalizada"],
        )
        if tasa_sel == "Personalizada":
            tasa_hcfp = st.number_input("h/CFP personalizados", 1.0, 50.0, 10.2, 0.1)
        else:
            tasa_hcfp = float(tasa_sel.split()[0].replace(",", "."))

    st.divider()

    # ── Tabla de procesos funcionales ────────────────────────────────────
    st.subheader("Procesos Funcionales y Movimientos de Datos")
    st.caption("Agrega tantos requerimientos funcionales (FUR) como necesites. Cada fila = 1 movimiento de datos.")

    if "cosmic_rows" not in st.session_state:
        st.session_state.cosmic_rows = [
            {"FUR": "Obtener detalles del profesor", "Usuario": "Registrador",
             "Descripcion_movimiento": "El registrador ingresa el ID del profesor",
             "Grupo_datos": "ID Profesor", "Tipo": "E"},
            {"FUR": "Obtener detalles del profesor", "Usuario": "Registrador",
             "Descripcion_movimiento": "El software obtiene los detalles",
             "Grupo_datos": "Detalles del profesor", "Tipo": "R"},
            {"FUR": "Obtener detalles del profesor", "Usuario": "Registrador",
             "Descripcion_movimiento": "El software presenta los detalles",
             "Grupo_datos": "Detalles del profesor", "Tipo": "X"},
            {"FUR": "Obtener detalles del profesor", "Usuario": "Registrador",
             "Descripcion_movimiento": "Mostrar mensaje de error",
             "Grupo_datos": "Mensaje de error", "Tipo": "X"},
        ]

    # Botón añadir fila
    col_add, col_clear = st.columns([1, 5])
    with col_add:
        if st.button("➕ Añadir movimiento"):
            st.session_state.cosmic_rows.append(
                {"FUR": "", "Usuario": "", "Descripcion_movimiento": "",
                 "Grupo_datos": "", "Tipo": "E"}
            )
    with col_clear:
        if st.button("🗑️ Limpiar tabla"):
            st.session_state.cosmic_rows = []

    # Renderizar filas editables
    headers = st.columns([3, 2, 4, 3, 1, 1])
    for h, t in zip(headers, ["FUR / Requerimiento", "Usuario Funcional",
                               "Descripción del Movimiento", "Grupo de Datos", "Tipo", "🗑️"]):
        h.markdown(f"**{t}**")

    rows_to_delete = []
    for idx, row in enumerate(st.session_state.cosmic_rows):
        c_fur, c_usr, c_desc, c_grp, c_tipo, c_del = st.columns([3, 2, 4, 3, 1, 1])
        row["FUR"]                  = c_fur.text_input("",  row["FUR"],  key=f"fur_{idx}",  label_visibility="collapsed")
        row["Usuario"]              = c_usr.text_input("",  row["Usuario"], key=f"usr_{idx}", label_visibility="collapsed")
        row["Descripcion_movimiento"] = c_desc.text_input("", row["Descripcion_movimiento"], key=f"desc_{idx}", label_visibility="collapsed")
        row["Grupo_datos"]          = c_grp.text_input("",  row["Grupo_datos"], key=f"grp_{idx}", label_visibility="collapsed")
        row["Tipo"]                 = c_tipo.selectbox("", ["E", "X", "R", "W"], index=["E","X","R","W"].index(row["Tipo"]),
                                                        key=f"tipo_{idx}", label_visibility="collapsed")
        if c_del.button("✕", key=f"del_{idx}"):
            rows_to_delete.append(idx)

    for idx in sorted(rows_to_delete, reverse=True):
        st.session_state.cosmic_rows.pop(idx)

    # ── Cálculo CFP ────────────────────────────────────────────────────────
    st.divider()
    rows = st.session_state.cosmic_rows
    total_cfp = len([r for r in rows if r["Tipo"] in ("E", "X", "R", "W")])

    # Conteo por tipo
    conteo = {t: sum(1 for r in rows if r["Tipo"] == t) for t in ["E", "X", "R", "W"]}

    # Resultados
    horas_base = total_cfp * tasa_hcfp
    st.subheader("Resultados COSMIC")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("CFP Total", f"{total_cfp} CFP")
    m2.metric("Entradas (E)", conteo["E"])
    m3.metric("Salidas (X)", conteo["X"])
    m4.metric("Lecturas (R)", conteo["R"])
    m5.metric("Escrituras (W)", conteo["W"])

    st.divider()

    # ── Factores de ajuste ────────────────────────────────────────────────
    st.subheader("Factores de Ajuste")
    factor_total = 1.0
    fa_valores   = {}
    cols_fa = st.columns(len(FACTORES_AJUSTE))
    for col, (nombre, rango) in zip(cols_fa, FACTORES_AJUSTE.items()):
        with col:
            v = st.slider(
                nombre,
                min_value=rango["min"], max_value=rango["max"],
                value=rango["ref"], step=0.05,
                key=f"fa_{nombre[:20]}",
                help=f"Min: {rango['min']} | Ref: {rango['ref']} | Máx: {rango['max']}",
            )
            fa_valores[nombre] = v
            factor_total *= v

    horas_ajustadas = horas_base * factor_total

    st.divider()
    r1, r2, r3 = st.columns(3)
    r1.metric("Horas base (sin ajuste)", f"{horas_base:,.1f} h",
              help=f"{total_cfp} CFP × {tasa_hcfp} h/CFP")
    r2.metric("Factor de ajuste compuesto", f"{factor_total:.3f}")
    r3.metric("⏱️ Horas estimadas TOTALES", f"{horas_ajustadas:,.1f} h",
              delta=f"{horas_ajustadas - horas_base:+.1f} h vs. base")

    # Gráfico distribución por tipo
    if total_cfp > 0:
        fig = go.Figure(go.Bar(
            x=["E", "X", "R", "W"],
            y=[conteo["E"], conteo["X"], conteo["R"], conteo["W"]],
            marker_color=[TIPO_MOVIMIENTO_COLOR[t] for t in ["E", "X", "R", "W"]],
            text=[conteo["E"], conteo["X"], conteo["R"], conteo["W"]],
            textposition="outside",
        ))
        fig.update_layout(
            title="Distribución de movimientos de datos",
            xaxis_title="Tipo", yaxis_title="Cantidad",
            height=280, plot_bgcolor="white",
            margin=dict(t=40, b=20, l=20, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla resumen FUR
        st.subheader("Resumen por Requerimiento Funcional")
        fur_df = (
            pd.DataFrame(rows)
            .groupby("FUR")
            .agg(CFP=("Tipo", "count"),
                 E=("Tipo", lambda x: (x == "E").sum()),
                 X=("Tipo", lambda x: (x == "X").sum()),
                 R=("Tipo", lambda x: (x == "R").sum()),
                 W=("Tipo", lambda x: (x == "W").sum()))
            .reset_index()
        )
        fur_df["Horas base"] = fur_df["CFP"] * tasa_hcfp
        st.dataframe(fur_df, use_container_width=True, hide_index=True)

    # ── Guardar en historial ───────────────────────────────────────────────
    st.divider()
    if st.button("💾 Guardar estimación COSMIC en historial", type="primary"):
        if not id_solicitud:
            st.warning("Ingresa el ID de solicitud antes de guardar.")
        else:
            _append_hist({
                "id_solicitud": id_solicitud,
                "modulo": "COSMIC",
                "sistema": nombre_fur,
                "cfp": total_cfp,
                "tasa_hcfp": tasa_hcfp,
                "factor_ajuste": round(factor_total, 3),
                "horas_estimadas": round(horas_ajustadas, 1),
            })
            st.success(f"Guardado: {id_solicitud} — {total_cfp} CFP — {horas_ajustadas:,.1f} h")


# ===========================================================================
# MÓDULO 2 — PERT
# ===========================================================================
elif modulo == "📊 PERT (Tres Puntos)":
    st.header("📊 Módulo PERT — Estimación de Tres Puntos")
    st.caption(
        "**E = (O + 4M + P) / 6** · σ = (P – O) / 6 · "
        "Basado en PMBOK 7ª Ed. y Mike Cohn — Agile Estimating and Planning"
    )

    c1, c2 = st.columns(2)
    with c1:
        id_solicitud_p = st.text_input("ID Solicitud", placeholder="SS-2025-002", key="pert_id")
    with c2:
        tipo_servicio_p = st.selectbox("Tipo de servicio", ["Desarrollo por producto", "Pruebas", "Provisión de perfiles"])

    st.divider()

    # ── Actividades ────────────────────────────────────────────────────────
    st.subheader("Actividades")
    if "pert_rows" not in st.session_state:
        st.session_state.pert_rows = [
            {"Actividad": "Diseño de casos de prueba",     "O": 16.0, "M": 24.0, "P": 40.0},
            {"Actividad": "Automatización de pruebas",     "O": 24.0, "M": 40.0, "P": 60.0},
            {"Actividad": "Ejecución y gestión defectos",  "O": 12.0, "M": 20.0, "P": 32.0},
        ]

    col_add_p, col_clr_p = st.columns([1, 5])
    with col_add_p:
        if st.button("➕ Añadir actividad"):
            st.session_state.pert_rows.append({"Actividad": "", "O": 0.0, "M": 0.0, "P": 0.0})
    with col_clr_p:
        if st.button("🗑️ Limpiar", key="pert_clear"):
            st.session_state.pert_rows = []

    headers_p = st.columns([4, 2, 2, 2, 2, 2, 1])
    for h, t in zip(headers_p, ["Actividad", "Optimista (O)", "Más probable (M)", "Pesimista (P)", "E (h)", "σ", "🗑️"]):
        h.markdown(f"**{t}**")

    rows_del_p = []
    for idx, row in enumerate(st.session_state.pert_rows):
        ca, co, cm, cp, ce, cs, cd = st.columns([4, 2, 2, 2, 2, 2, 1])
        row["Actividad"] = ca.text_input("", row["Actividad"], key=f"pact_{idx}", label_visibility="collapsed")
        row["O"] = co.number_input("", 0.0, 9999.0, float(row["O"]), 1.0, key=f"po_{idx}", label_visibility="collapsed")
        row["M"] = cm.number_input("", 0.0, 9999.0, float(row["M"]), 1.0, key=f"pm_{idx}", label_visibility="collapsed")
        row["P"] = cp.number_input("", 0.0, 9999.0, float(row["P"]), 1.0, key=f"pp_{idx}", label_visibility="collapsed")
        e_val, s_val = _pert(row["O"], row["M"], row["P"])
        ce.metric("", f"{e_val:.1f}")
        cs.metric("", f"{s_val:.1f}")
        if cd.button("✕", key=f"pdel_{idx}"):
            rows_del_p.append(idx)

    for idx in sorted(rows_del_p, reverse=True):
        st.session_state.pert_rows.pop(idx)

    # ── Totales PERT ───────────────────────────────────────────────────────
    st.divider()
    if st.session_state.pert_rows:
        sum_O = sum(r["O"] for r in st.session_state.pert_rows)
        sum_M = sum(r["M"] for r in st.session_state.pert_rows)
        sum_P = sum(r["P"] for r in st.session_state.pert_rows)
        E_total, sigma_total = _pert(sum_O, sum_M, sum_P)
        # σ combinado correctamente = sqrt(Σ σ_i²)
        sigma_comb = math.sqrt(
            sum(_pert(r["O"], r["M"], r["P"])[1] ** 2 for r in st.session_state.pert_rows)
        )

        st.subheader("Resultados PERT")
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("Σ Optimista",      f"{sum_O:.0f} h")
        p2.metric("Σ Más probable",   f"{sum_M:.0f} h")
        p3.metric("Σ Pesimista",      f"{sum_P:.0f} h")
        p4.metric("⏱️ E total (h)",   f"{E_total:.1f} h")
        p5.metric("σ combinado",      f"{sigma_comb:.1f} h")

        st.divider()
        st.markdown(
            f"**Intervalo de confianza:**  "
            f"68% → [{E_total - sigma_comb:.0f} – {E_total + sigma_comb:.0f}] h  ·  "
            f"95% → [{E_total - 2*sigma_comb:.0f} – {E_total + 2*sigma_comb:.0f}] h"
        )

        # Gráfico tornado
        e_vals = [_pert(r["O"], r["M"], r["P"])[0] for r in st.session_state.pert_rows]
        acts   = [r["Actividad"] or f"Act. {i+1}" for i, r in enumerate(st.session_state.pert_rows)]
        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(
            name="Optimista", y=acts,
            x=[r["O"] for r in st.session_state.pert_rows],
            orientation="h", marker_color="#307B47",
        ))
        fig_p.add_trace(go.Bar(
            name="E (esperado)", y=acts, x=e_vals,
            orientation="h", marker_color="#0070F2",
        ))
        fig_p.add_trace(go.Bar(
            name="Pesimista", y=acts,
            x=[r["P"] for r in st.session_state.pert_rows],
            orientation="h", marker_color="#BB0000",
        ))
        fig_p.update_layout(
            barmode="overlay", title="Rango de estimación por actividad",
            xaxis_title="Horas", height=300 + len(acts)*30,
            plot_bgcolor="white", margin=dict(t=40, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_p, use_container_width=True)

        st.divider()
        if st.button("💾 Guardar estimación PERT en historial", type="primary"):
            if not id_solicitud_p:
                st.warning("Ingresa el ID de solicitud.")
            else:
                _append_hist({
                    "id_solicitud": id_solicitud_p,
                    "modulo": "PERT",
                    "tipo_servicio": tipo_servicio_p,
                    "horas_estimadas": round(E_total, 1),
                    "sigma": round(sigma_comb, 1),
                    "sum_O": sum_O, "sum_M": sum_M, "sum_P": sum_P,
                })
                st.success(f"Guardado: {id_solicitud_p} — E = {E_total:.1f} h (σ = {sigma_comb:.1f} h)")


# ===========================================================================
# MÓDULO 3 — COMPLEJIDAD DE COMPONENTES
# ===========================================================================
elif modulo == "🔧 Complejidad de Componentes":
    st.header("🔧 Módulo de Complejidad de Componentes")
    st.caption(
        "Para requerimientos técnicos no funcionales: migraciones, integraciones, "
        "CI/CD, arquitectura de nube. Basado en SNAP v2.4 (IFPUG) y SDP 5.4.2."
    )

    c1, c2 = st.columns(2)
    with c1:
        id_comp = st.text_input("ID Solicitud", placeholder="SS-2025-003", key="comp_id")
    with c2:
        nombre_comp = st.text_input("Nombre del componente", placeholder="Pipeline CI/CD - Sistema tributario")

    st.divider()

    if "comp_rows" not in st.session_state:
        st.session_state.comp_rows = [
            {"Componente": "Integración con ESB DIAN", "Complejidad": "Media",
             "N_integraciones": 3, "Volumen_datos": "Medio",
             "Nivel_seguridad": "Alto", "Req_rendimiento": "Medio"}
        ]

    col_add_c, col_clr_c = st.columns([1, 5])
    with col_add_c:
        if st.button("➕ Añadir componente"):
            st.session_state.comp_rows.append({
                "Componente": "", "Complejidad": "Media",
                "N_integraciones": 1, "Volumen_datos": "Bajo",
                "Nivel_seguridad": "Bajo", "Req_rendimiento": "Bajo",
            })
    with col_clr_c:
        if st.button("🗑️ Limpiar", key="comp_clear"):
            st.session_state.comp_rows = []

    # Factores de ajuste SNAP
    FA_INTEG  = {"0-1": 1.0, "2-3": 1.1, "4-6": 1.2, ">6": 1.35}
    FA_VOL    = {"Bajo": 1.0, "Medio": 1.1, "Alto": 1.2}
    FA_SEG    = {"Bajo": 1.0, "Medio": 1.1, "Alto": 1.25}
    FA_REND   = {"Bajo": 1.0, "Medio": 1.05, "Alto": 1.15}

    def _fa_integ(n: int) -> float:
        if n <= 1:  return FA_INTEG["0-1"]
        if n <= 3:  return FA_INTEG["2-3"]
        if n <= 6:  return FA_INTEG["4-6"]
        return FA_INTEG[">6"]

    headers_c = st.columns([3, 2, 2, 2, 2, 2, 2])
    for h, t in zip(headers_c, ["Componente", "Complejidad", "N° integ.", "Vol. datos", "Seguridad", "Rendimiento", "🗑️"]):
        h.markdown(f"**{t}**")

    rows_del_c = []
    for idx, row in enumerate(st.session_state.comp_rows):
        cn, cc, ci, cv, cs2, cr, cd = st.columns([3, 2, 2, 2, 2, 2, 2])
        row["Componente"]     = cn.text_input("",  row["Componente"],  key=f"cn_{idx}", label_visibility="collapsed")
        row["Complejidad"]    = cc.selectbox("",  ["Baja","Media","Alta"],
                                              index=["Baja","Media","Alta"].index(row["Complejidad"]),
                                              key=f"cc_{idx}", label_visibility="collapsed")
        row["N_integraciones"] = ci.number_input("", 0, 20, int(row["N_integraciones"]),
                                                  key=f"ci_{idx}", label_visibility="collapsed")
        row["Volumen_datos"]  = cv.selectbox("",  ["Bajo","Medio","Alto"],
                                              index=["Bajo","Medio","Alto"].index(row["Volumen_datos"]),
                                              key=f"cvd_{idx}", label_visibility="collapsed")
        row["Nivel_seguridad"] = cs2.selectbox("", ["Bajo","Medio","Alto"],
                                                index=["Bajo","Medio","Alto"].index(row["Nivel_seguridad"]),
                                                key=f"cns_{idx}", label_visibility="collapsed")
        row["Req_rendimiento"] = cr.selectbox("", ["Bajo","Medio","Alto"],
                                               index=["Bajo","Medio","Alto"].index(row["Req_rendimiento"]),
                                               key=f"crr_{idx}", label_visibility="collapsed")
        if cd.button("✕", key=f"cdel_{idx}"):
            rows_del_c.append(idx)

    for idx in sorted(rows_del_c, reverse=True):
        st.session_state.comp_rows.pop(idx)

    st.divider()
    # Calcular y mostrar
    st.subheader("Resultados por Componente")
    total_comp_h = 0.0
    result_rows  = []
    for row in st.session_state.comp_rows:
        comp = row["Complejidad"]
        rmin, rmax, _ = COMP_RANGOS[comp]
        rbase = (rmin + rmax) / 2
        fa = (_fa_integ(row["N_integraciones"]) *
              FA_VOL[row["Volumen_datos"]] *
              FA_SEG[row["Nivel_seguridad"]] *
              FA_REND[row["Req_rendimiento"]])
        h_est = rbase * fa
        total_comp_h += h_est
        result_rows.append({
            "Componente":   row["Componente"] or f"Comp. {len(result_rows)+1}",
            "Complejidad":  comp,
            "Rango base":   f"{rmin}–{rmax} h",
            "FA total":     round(fa, 3),
            "Horas estimadas": round(h_est, 1),
        })

    if result_rows:
        df_comp = pd.DataFrame(result_rows)

        def _style_comp(val):
            return {"Baja": "color:#307B47", "Media": "color:#E6A117",
                    "Alta": "color:#BB0000"}.get(val, "")

        st.dataframe(
            df_comp.style.applymap(_style_comp, subset=["Complejidad"]),
            use_container_width=True, hide_index=True
        )

        st.metric("⏱️ Total horas estimadas", f"{total_comp_h:,.1f} h")

        fig_c = px.bar(
            df_comp, x="Componente", y="Horas estimadas",
            color="Complejidad",
            color_discrete_map={"Baja": "#307B47", "Media": "#E6A117", "Alta": "#BB0000"},
            text="Horas estimadas",
        )
        fig_c.update_traces(texttemplate="%{text:.0f}h", textposition="outside")
        fig_c.update_layout(
            title="Horas por componente", plot_bgcolor="white",
            height=320, margin=dict(t=40, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_c, use_container_width=True)

    st.divider()
    if st.button("💾 Guardar en historial", type="primary", key="comp_save"):
        if not id_comp:
            st.warning("Ingresa el ID de solicitud.")
        else:
            _append_hist({
                "id_solicitud": id_comp,
                "modulo": "Complejidad",
                "sistema": nombre_comp,
                "n_componentes": len(st.session_state.comp_rows),
                "horas_estimadas": round(total_comp_h, 1),
            })
            st.success(f"Guardado: {id_comp} — {total_comp_h:,.1f} h")


# ===========================================================================
# MÓDULO 4 — DISTRIBUCIÓN SDLC
# ===========================================================================
elif modulo == "📋 Distribución SDLC":
    st.header("📋 Distribución de Esfuerzo por Fases SDLC")
    st.caption(
        "SDP 5.4.2 Req. 2 · Fuente: ISBSG 2024, COCOMO II, BID LATAM 2023 · "
        "Desvíos >15% en cualquier fase requieren justificación."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        complejidad_sdlc = st.selectbox("Complejidad del proyecto", ["Baja", "Media", "Alta"])
    with c2:
        horas_totales_sdlc = st.number_input(
            "Horas totales estimadas", 0.0, 100000.0, 500.0, 10.0,
            help="Ingresa el total de horas calculadas en COSMIC, PERT o Complejidad"
        )
    with c3:
        tarifa_hora = st.number_input("Tarifa por hora (USD, opcional)", 0.0, 500.0, 0.0, 5.0)

    st.divider()

    dist = DIST_SDLC
    comp = complejidad_sdlc
    rows_sdlc = []
    for fase, porcs in dist.items():
        porc = porcs[comp] / 100
        horas = horas_totales_sdlc * porc
        costo = horas * tarifa_hora if tarifa_hora > 0 else None
        rows_sdlc.append({
            "Fase SDLC": fase,
            "% Referencia": f"{porcs[comp]}%",
            "Horas": round(horas, 1),
            **({"Costo (USD)": f"${costo:,.0f}" if costo else "-"} if tarifa_hora > 0 else {}),
        })

    df_sdlc = pd.DataFrame(rows_sdlc)
    st.dataframe(df_sdlc, use_container_width=True, hide_index=True)

    # Gráfico donut
    fig_sdlc = go.Figure(go.Pie(
        labels=[r["Fase SDLC"] for r in rows_sdlc],
        values=[r["Horas"] for r in rows_sdlc],
        hole=0.5,
        textinfo="label+percent",
        hovertemplate="%{label}<br>%{value:.0f} h (%{percent})<extra></extra>",
    ))
    fig_sdlc.update_layout(
        title=f"Distribución de esfuerzo — Complejidad {comp}",
        height=400, margin=dict(t=40, b=20, l=20, r=20),
        showlegend=False,
    )
    fig_sdlc.add_annotation(
        text=f"<b>{horas_totales_sdlc:,.0f} h</b><br>total",
        x=0.5, y=0.5, showarrow=False, font=dict(size=14),
    )
    st.plotly_chart(fig_sdlc, use_container_width=True)

    if tarifa_hora > 0:
        st.metric("Costo total estimado", f"${horas_totales_sdlc * tarifa_hora:,.0f} USD")


# ===========================================================================
# MÓDULO 5 — COMPARACIÓN CONTRATISTA vs. INTERVENTORÍA
# ===========================================================================
elif modulo == "⚖️ Comparación Contratista":
    st.header("⚖️ Módulo de Comparación — Regla del 10%")
    st.caption(
        "SDP 5.4.2 Req. 6 · Desviación = (Est.Contratista – Est.Interventoría) / Est.Interventoría × 100 · "
        "**>10%** → Rechazar (ANS 9) · **0–10%** → Promedio · **≤0%** → Aprobar"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        id_comp_r = st.text_input("ID Solicitud", placeholder="SS-2025-001", key="rev_id")
    with c2:
        metodo_cont = st.selectbox("Método del Contratista",
                                   ["COSMIC", "Complejidad de Componentes", "Juicio Experto", "Otro"])
    with c3:
        metodo_int  = st.selectbox("Método de la Interventoría",
                                   ["COSMIC", "PERT", "Complejidad de Componentes", "Combinado"])

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏭 Contratista")
        est_cont = st.number_input("Horas estimadas (Contratista)", 0.0, 99999.0, 520.0, 10.0)
        cfp_cont = st.number_input("CFP declarados (si aplica)", 0, 9999, 0)
        st.caption(f"Tasa implícita: {est_cont/cfp_cont:.1f} h/CFP" if cfp_cont > 0 else "")

    with col_b:
        st.subheader("🔍 Interventoría")
        est_int = st.number_input("Horas estimadas (Interventoría)", 0.0, 99999.0, 480.0, 10.0)
        cfp_int = st.number_input("CFP contados (si aplica)", 0, 9999, 0, key="cfp_int")
        st.caption(f"Tasa implícita: {est_int/cfp_int:.1f} h/CFP" if cfp_int > 0 else "")

    st.divider()

    if est_int > 0:
        desv = _desviacion(est_cont, est_int)
        abs_desv = abs(desv)

        # Decisión
        if desv <= 0:
            decision_txt  = "✅ APROBADA — La estimación del Contratista es igual o menor a la de la Interventoría."
            decision_cls  = "decision-aprobada"
            horas_acordadas = est_cont
        elif abs_desv <= 10:
            horas_acordadas = (est_cont + est_int) / 2
            decision_txt  = f"🟡 APROBADA (PROMEDIO) — Diferencia de {abs_desv:.1f}% ≤ 10%. Valor acordado = promedio simple."
            decision_cls  = "decision-promedio"
        else:
            horas_acordadas = 0.0
            decision_txt  = f"🔴 RECHAZADA — Diferencia de {abs_desv:.1f}% > 10%. El Contratista tiene 3 días hábiles para revisar. Activar ANS 9 si es la 3ª vez."
            decision_cls  = "decision-rechazada"

        # Métricas
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Est. Contratista", f"{est_cont:,.1f} h")
        m2.metric("Est. Interventoría", f"{est_int:,.1f} h")
        m3.metric("Desviación", f"{desv:+.1f}%",
                  delta_color="inverse" if desv > 10 else "normal")
        m4.metric("Horas acordadas", f"{horas_acordadas:,.1f} h" if horas_acordadas > 0 else "—")

        st.markdown(
            f"<div class='{decision_cls}'>{decision_txt}</div>",
            unsafe_allow_html=True
        )

        # Barra visual de desviación
        st.divider()
        fig_d = go.Figure()
        fig_d.add_vrect(x0=-10, x1=0,    fillcolor="#d4edda", opacity=0.3, line_width=0, annotation_text="Aprobada")
        fig_d.add_vrect(x0=0,   x1=10,   fillcolor="#fff3cd", opacity=0.3, line_width=0, annotation_text="Promedio")
        fig_d.add_vrect(x0=10,  x1=max(abs_desv*1.5, 20), fillcolor="#f8d7da", opacity=0.3, line_width=0, annotation_text="Rechazada")
        fig_d.add_vline(x=0,    line_dash="dash", line_color="#888", line_width=1)
        fig_d.add_vline(x=desv, line_color="#001F5B", line_width=3,
                        annotation_text=f"Desviación: {desv:+.1f}%",
                        annotation_position="top")
        fig_d.update_layout(
            title="Posición de la desviación respecto a los umbrales",
            xaxis_title="Desviación (%)", height=200,
            xaxis=dict(range=[min(desv*1.5, -15), max(desv*1.5, 25)]),
            yaxis=dict(visible=False), plot_bgcolor="white",
            margin=dict(t=50, b=30, l=20, r=20),
        )
        st.plotly_chart(fig_d, use_container_width=True)

        # Notas técnicas
        st.subheader("Observaciones técnicas")
        obs_text = st.text_area(
            "Justificación / Comentarios",
            placeholder="Ej: La diferencia se explica por X factores técnicos...",
            height=100,
        )
        iteracion = st.selectbox("N° de iteración", [1, 2, 3])

        st.divider()
        if st.button("💾 Guardar revisión en historial", type="primary"):
            if not id_comp_r:
                st.warning("Ingresa el ID de solicitud.")
            else:
                _append_hist({
                    "id_solicitud": id_comp_r,
                    "modulo": "Comparación",
                    "est_contratista": est_cont,
                    "est_interventoria": est_int,
                    "desviacion_pct": round(desv, 2),
                    "decision": "APROBADA" if desv <= 0 else ("PROMEDIO" if abs_desv <= 10 else "RECHAZADA"),
                    "horas_acordadas": round(horas_acordadas, 1),
                    "iteracion": iteracion,
                    "observaciones": obs_text,
                    "horas_estimadas": round(horas_acordadas, 1),
                })
                st.success(f"Revisión guardada: {id_comp_r}")


# ===========================================================================
# MÓDULO 6 — HISTORIAL
# ===========================================================================
elif modulo == "📁 Historial":
    st.header("📁 Historial de Estimaciones")
    st.caption("Registro acumulado para calibración continua y análisis de tendencias.")

    records = _load_hist()

    if not records:
        st.info("No hay estimaciones guardadas aún. Usa los módulos anteriores para generar y guardar estimaciones.")
    else:
        df_hist = pd.DataFrame(records)

        # ── Filtros ────────────────────────────────────────────────────────
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            modulos_disp = ["Todos"] + sorted(df_hist["modulo"].unique().tolist())
            filtro_modulo = st.selectbox("Filtrar por módulo", modulos_disp)
        with col_f2:
            busqueda = st.text_input("Buscar por ID o sistema", "")
        with col_f3:
            st.metric("Total estimaciones", len(records))

        df_show = df_hist.copy()
        if filtro_modulo != "Todos":
            df_show = df_show[df_show["modulo"] == filtro_modulo]
        if busqueda:
            mask = df_show.apply(lambda row: busqueda.lower() in str(row).lower(), axis=1)
            df_show = df_show[mask]

        # ── Tabla ──────────────────────────────────────────────────────────
        cols_show = [c for c in ["fecha", "id_solicitud", "modulo", "sistema",
                                  "horas_estimadas", "cfp", "desviacion_pct", "decision"]
                     if c in df_show.columns]
        st.dataframe(df_show[cols_show].sort_values("fecha", ascending=False),
                     use_container_width=True, hide_index=True)

        # ── Gráfico tendencias ─────────────────────────────────────────────
        if "horas_estimadas" in df_hist.columns and len(df_hist) >= 2:
            st.divider()
            st.subheader("Tendencia de estimaciones")
            df_trend = df_hist.dropna(subset=["horas_estimadas"]).copy()
            df_trend["fecha_dt"] = pd.to_datetime(df_trend["fecha"], errors="coerce")
            df_trend = df_trend.dropna(subset=["fecha_dt"]).sort_values("fecha_dt")

            fig_t = px.scatter(
                df_trend, x="fecha_dt", y="horas_estimadas",
                color="modulo", size_max=12,
                hover_data=["id_solicitud"],
                labels={"fecha_dt": "Fecha", "horas_estimadas": "Horas estimadas"},
                title="Histórico de estimaciones por módulo",
            )
            fig_t.update_layout(plot_bgcolor="white", height=320,
                                 margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_t, use_container_width=True)

        # ── Estadísticas ───────────────────────────────────────────────────
        if "horas_estimadas" in df_hist.columns:
            st.divider()
            st.subheader("Estadísticas globales")
            h_vals = df_hist["horas_estimadas"].dropna()
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Promedio horas", f"{h_vals.mean():,.1f}")
            s2.metric("Mediana horas",  f"{h_vals.median():,.1f}")
            s3.metric("Mínimo",         f"{h_vals.min():,.1f}")
            s4.metric("Máximo",         f"{h_vals.max():,.1f}")

        # ── Descargar ──────────────────────────────────────────────────────
        st.divider()
        csv_data = df_show[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar historial CSV",
            data=csv_data,
            file_name=f"historial_cosmic_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        if st.button("🗑️ Borrar TODO el historial", type="secondary"):
            _save_hist([])
            st.success("Historial borrado.")
            st.rerun()
