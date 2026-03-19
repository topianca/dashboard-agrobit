import streamlit as st
import pandas as pd
import psycopg2
import time
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="top1nfo — Inteligência Agro",
    page_icon="☕",
    layout="wide"
)

DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

# ============================================================
# 2. FUNÇÕES AUXILIARES
# ============================================================
def calcular_ponto_orvalho(T, RH):
    b, c  = 17.67, 243.5
    gamma = (b * T / (c + T)) + np.log(max(RH, 0.01) / 100.0)
    return round((c * gamma) / (b - gamma), 1)


def calcular_sensacao_termica(T, RH):
    if T < 20:
        return round(T, 1)
    hi = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    return round(hi, 1)

# ============================================================
# 3. QUERIES AO BANCO
# ============================================================
@st.cache_data(ttl=20)
def carregar_dados(d1, d2):
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT data_hora, temperatura, umidade, sensor_id
            FROM leituras_cafe
            WHERE data_hora::date BETWEEN %s AND %s
            ORDER BY data_hora DESC
            LIMIT 5000
            """,
            (str(d1), str(d2))
        )
        rows = cursor.fetchall()
        conn.close()

        df = pd.DataFrame(rows, columns=["data_hora", "temperatura", "umidade", "sensor_id"])
        if df.empty:
            return df

        dt = pd.to_datetime(df["data_hora"])
        if dt.dt.tz is not None:
            df["data_hora"] = dt.dt.tz_convert("UTC").dt.tz_localize(None)
        else:
            df["data_hora"] = dt

        return df
    except Exception as e:
        st.error(f"Erro de conexão com o banco: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def carregar_horas_frio():
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE_TRUNC('hour', data_hora))
            FROM leituras_cafe
            WHERE temperatura < 10
              AND data_hora >= NOW() - INTERVAL '90 days'
        """)
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] else 0
    except Exception:
        return 0


@st.cache_data(ttl=120)
def carregar_sensores_disponiveis():
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sensor_id FROM leituras_cafe ORDER BY sensor_id")
        rows = cursor.fetchall()
        conn.close()
        return ["Todos"] + [r[0] for r in rows]
    except Exception:
        return ["Todos", "ESP32_Fazenda"]

# ============================================================
# 4. LOGIN
# ============================================================
def verifica_senha():
    SENHA_CORRETA = "agrobit2026"
    if "autenticado" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🔒 top1nfo — Área Restrita")
            st.markdown("Sistema de Inteligência Cafeeira — Pedra Bonita, MG")
            senha = st.text_input("Senha de Acesso:", type="password")
            if st.button("Entrar", use_container_width=True):
                if senha == SENHA_CORRETA:
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("❌ Acesso negado.")
        return False
    return True

# ============================================================
# 5. EXECUÇÃO PRINCIPAL
# ============================================================
if not verifica_senha():
    st.stop()

# BARRA LATERAL
st.sidebar.markdown("## ☕ top1nfo")
st.sidebar.markdown("**Pedra Bonita — Matas de Minas**")
st.sidebar.divider()
st.sidebar.header("🗓️ Filtros")
hoje  = datetime.now()
ontem = hoje - timedelta(days=1)
data_ini = st.sidebar.date_input("Data Inicial", ontem)
data_fim = st.sidebar.date_input("Data Final",   hoje)

sensor_opcoes      = carregar_sensores_disponiveis()
sensor_selecionado = st.sidebar.selectbox("🌡️ Sensor", sensor_opcoes)

if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🚪 Logoff"):
    del st.session_state["autenticado"]
    st.rerun()

# CARREGAMENTO
df_completo = carregar_dados(data_ini, data_fim)

if sensor_selecionado != "Todos" and not df_completo.empty:
    df = df_completo[df_completo["sensor_id"] == sensor_selecionado].copy()
else:
    df = df_completo.copy()

# CABEÇALHO
st.title("🚜 Painel de Inteligência Cafeeira")
st.markdown("Monitoramento de precisão **top1nfo** — Córrego do Café, Pedra Bonita MG")
st.divider()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado para o período e sensor selecionados.")
    st.stop()

# ============================================================
# 6. PROCESSAMENTO
# ============================================================
atual    = df.iloc[0]
anterior = df.iloc[1] if len(df) > 1 else atual

T  = float(atual["temperatura"])
H  = float(atual["umidade"])
dT = round(T - float(anterior["temperatura"]), 1)
dH = round(H - float(anterior["umidade"]), 1)

orvalho    = calcular_ponto_orvalho(T, H)
sensacao   = calcular_sensacao_termica(T, H)
horas_frio = carregar_horas_frio()

risco_geada       = T <= 4.0
risco_phoma       = 10.0 <= T <= 18.0 and H > 85.0
risco_ferrugem    = 18.0 <= T <= 24.0 and H > 90.0
risco_escaldadura = T >= 32.0

# ============================================================
# 7. KPIs
# ============================================================
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🌡️ Temperatura",     f"{T} °C",       f"{dT} °C",   delta_color="inverse")
c2.metric("💧 Umidade Relativa", f"{H} %",        f"{dH} %")
c3.metric("🌫️ Ponto de Orvalho", f"{orvalho} °C", "Folha Seca" if T > orvalho + 2 else "⚠️ Risco Orvalho")
c4.metric("🌡️ Sensação Térmica", f"{sensacao} °C")
c5.metric("❄️ Horas de Frio",    f"{horas_frio} h",
          help="Últimos 90 dias | Meta: 200h para florada uniforme do Arábica")

st.divider()

# ============================================================
# 8. ALERTAS — SOMENTE VISUAL, SEM WHATSAPP
# CORREÇÃO: WhatsApp removido do dashboard.
# O Worker já envia alertas 24h/dia com cooldown correto.
# Manter aqui causava alertas duplicados a cada nova sessão.
# ============================================================
st.subheader("🚨 Alertas de Campo")
algum_alerta = False

agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
diff_min  = max(0.0, (agora_utc - atual["data_hora"]).total_seconds() / 60)

if diff_min > 20:
    algum_alerta = True
    st.error(
        f"📡 **SENSOR OFFLINE** — Última leitura há {int(diff_min)} minutos. "
        "Verifique o ESP32 e a conexão Wi-Fi."
    )

if risco_geada:
    algum_alerta = True
    st.error(
        f"❄️ **RISCO DE GEADA** — {T}°C detectado\n\n"
        "**Plano de Ação:** Mantenha as ruas limpas para escoamento do ar frio. "
        "Chegue terra no tronco das plantas novas. Evite irrigação noturna."
    )

if risco_phoma:
    algum_alerta = True
    st.warning(
        f"🍄 **RISCO DE PHOMA** — {T}°C com {H}% de umidade\n\n"
        "**Plano de Ação:** Vistorie brotações novas nas próximas 48h. "
        "Lesões escuras nos ramos = aplique cúpricos. Priorize lavouras em encosta."
    )

if risco_ferrugem:
    algum_alerta = True
    st.warning(
        f"🟠 **RISCO DE FERRUGEM TARDIA** — {T}°C com {H}% de umidade\n\n"
        "**Plano de Ação:** Amostragem foliar em 20 plantas. "
        "Se incidência > 5%, aplique fungicida sistêmico. Registre data e produto."
    )

if risco_escaldadura:
    algum_alerta = True
    st.warning(
        f"🔥 **RISCO DE ESCALDADURA** — {T}°C\n\n"
        "**Plano de Ação:** NÃO roçar a braquiária nas entrelinhas agora. "
        "Cobertura vegetal protege a raiz. Irrigação somente pela manhã."
    )

if not algum_alerta:
    st.success("✅ Nenhum risco agronômico detectado. Lavoura em condições normais.")

st.divider()

# ============================================================
# 9. GRÁFICO
# ============================================================
col_g1, col_g2 = st.columns([3, 1])

with col_g1:
    st.markdown("### 📈 Evolução Climática")
    df_graf = df.sort_values("data_hora")
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_graf["data_hora"], y=df_graf["temperatura"],
        name="Temperatura (°C)", line=dict(color="#E05C2A", width=2), mode="lines"
    ))
    fig.add_trace(go.Scatter(
        x=df_graf["data_hora"], y=df_graf["umidade"],
        name="Umidade (%)", line=dict(color="#2A7AE0", width=2, dash="dot"),
        mode="lines", yaxis="y2"
    ))
    fig.add_hline(y=4,  line=dict(color="cyan", width=1.5, dash="dash"),
                  annotation_text="⚠️ Geada (4°C)",   annotation_position="bottom right",
                  annotation_font_color="cyan")
    fig.add_hline(y=32, line=dict(color="red",  width=1.5, dash="dash"),
                  annotation_text="🔥 Escaldadura (32°C)", annotation_position="top right",
                  annotation_font_color="red")
    fig.update_layout(
        height=420,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Horário", gridcolor="#333"),
        yaxis=dict(title="Temperatura (°C)", side="left", gridcolor="#333"),
        yaxis2=dict(title="Umidade (%)", overlaying="y", side="right", gridcolor="#333"),
        margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

with col_g2:
    st.markdown("### 📋 Resumo do Período")
    st.markdown(f"**Máxima:** {df['temperatura'].max():.1f} °C")
    st.markdown(f"**Mínima:** {df['temperatura'].min():.1f} °C")
    st.markdown(f"**Média:** {df['temperatura'].mean():.1f} °C")
    st.markdown(f"**Umidade Máx:** {df['umidade'].max():.1f} %")
    st.markdown(f"**Umidade Mín:** {df['umidade'].min():.1f} %")
    st.markdown(f"**Sensação Atual:** {sensacao} °C")
    st.markdown(f"**Ponto de Orvalho:** {orvalho} °C")
    st.markdown(f"**❄️ Horas de Frio (90d):** {horas_frio} h")
    st.markdown(f"**Registros:** {len(df)}")

    META_HORAS_FRIO = 200
    st.markdown("---")
    st.markdown("**Acúmulo para Florada:**")
    progresso = min(horas_frio / META_HORAS_FRIO, 1.0)
    st.progress(progresso)
    st.caption(f"{horas_frio}/{META_HORAS_FRIO}h ({int(progresso * 100)}%)")

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📊 Baixar CSV", data=csv,
        file_name=f"top1nfo_{data_ini}_{data_fim}.csv",
        mime="text/csv", use_container_width=True
    )

# ============================================================
# 10. LOG DE AUDITORIA
# ============================================================
st.divider()
with st.expander("🔍 Log de Auditoria Completo"):
    sensores_no_periodo = df["sensor_id"].unique().tolist()
    st.caption(f"Sensores neste período: {', '.join(sensores_no_periodo)}")
    st.dataframe(
        df[["data_hora", "temperatura", "umidade", "sensor_id"]],
        use_container_width=True, hide_index=True
    )
