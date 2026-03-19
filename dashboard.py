import streamlit as st
import pandas as pd
import psycopg2
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="top1nfo — Inteligência Agro", page_icon="☕", layout="wide")

DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

def calcular_ponto_orvalho(T, RH):
    b, c = 17.67, 243.5
    gamma = (b * T / (c + T)) + np.log(max(RH, 0.01) / 100.0)
    return round((c * gamma) / (b - gamma), 1)

def calcular_sensacao_termica(T, RH):
    if T < 20: return round(T, 1)
    return round(0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094)), 1)

@st.cache_data(ttl=20)
def carregar_dados(d1, d2):
    try:
        conn = psycopg2.connect(DB_URL)
        query = """
            SELECT data_hora, temperatura, umidade, sensor_id 
            FROM leituras_cafe 
            WHERE data_hora::date BETWEEN %s AND %s 
            ORDER BY data_hora DESC LIMIT 5000
        """
        df = pd.read_sql_query(query, conn, params=(str(d1), str(d2)))
        conn.close()
        
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            if df['data_hora'].dt.tz is not None:
                df['data_hora'] = df['data_hora'].dt.tz_convert("UTC").dt.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"Erro BD: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_horas_frio():
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT DATE_TRUNC('hour', data_hora)) FROM leituras_cafe WHERE temperatura < 10 AND data_hora >= NOW() - INTERVAL '90 days'")
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] else 0
    except: return 0

def verifica_senha():
    if "autenticado" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🔒 top1nfo — Área Restrita")
            if st.button("Acessar Painel (Modo Dev)", use_container_width=True):
                st.session_state["autenticado"] = True
                st.rerun()
        return False
    return True

if not verifica_senha(): st.stop()

# BARRA LATERAL
st.sidebar.markdown("## ☕ top1nfo\n**Córrego do Café, MG**")
st.sidebar.divider()
data_ini = st.sidebar.date_input("Data Inicial", datetime.now() - timedelta(days=1))
data_fim = st.sidebar.date_input("Data Final", datetime.now())

if st.sidebar.button("🔄 Atualizar"): 
    st.cache_data.clear()
    st.rerun()

df = carregar_dados(data_ini, data_fim)

st.title("🚜 Painel de Inteligência Cafeeira")
st.divider()

if df.empty:
    st.warning("⚠️ Nenhum dado de sensor gravado para estas datas.")
    st.stop()

atual = df.iloc[0]
T, H = float(atual["temperatura"]), float(atual["umidade"])
dT = round(T - float(df.iloc[1]["temperatura"]), 1) if len(df) > 1 else 0

horas_frio = carregar_horas_frio()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🌡️ Temperatura", f"{T} °C", f"{dT} °C", delta_color="inverse")
c2.metric("💧 Umidade", f"{H} %")
c3.metric("🌫️ Ponto Orvalho", f"{calcular_ponto_orvalho(T, H)} °C")
c4.metric("🌡️ Sensação Térmica", f"{calcular_sensacao_termica(T, H)} °C")
c5.metric("❄️ Horas de Frio", f"{horas_frio} h", help="Meta: 200h (Últimos 90 dias)")

st.divider()

col_g1, col_g2 = st.columns([3, 1])

with col_g1:
    st.markdown("### 📈 Evolução Climática")
    df_graf = df.sort_values("data_hora")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_graf["data_hora"], y=df_graf["temperatura"], name="Temp (°C)", line=dict(color="#E05C2A", width=2)))
    fig.add_trace(go.Scatter(x=df_graf["data_hora"], y=df_graf["umidade"], name="Umidade (%)", line=dict(color="#2A7AE0", width=2, dash="dot"), yaxis="y2"))
    
    fig.add_hline(y=4, line=dict(color="cyan", width=1.5, dash="dash"), annotation_text="⚠️ Geada (4°C)")
    fig.add_hline(y=32, line=dict(color="red", width=1.5, dash="dash"), annotation_text="🔥 Escaldadura (32°C)")
    
    fig.update_layout(height=420, yaxis2=dict(overlaying="y", side="right"), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

with col_g2:
    st.markdown("### 📋 Alertas Ativos")
    if T <= 4.0: st.error("❄️ **RISCO DE GEADA**")
    elif T >= 32.0: st.warning("🔥 **RISCO ESCALDADURA**")
    elif 10.0 <= T <= 18.0 and H > 85.0: st.warning("🍄 **RISCO PHOMA**")
    elif 18.0 <= T <= 24.0 and H > 90.0: st.warning("🟠 **RISCO FERRUGEM**")
    else: st.success("✅ Condições Normais")
    
    st.download_button("📊 Baixar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="dados.csv", use_container_width=True)

with st.expander("🔍 Log de Auditoria"):
    st.dataframe(df[["data_hora", "temperatura", "umidade", "sensor_id"]], use_container_width=True)
