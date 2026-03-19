import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
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

# Anti-spam: cooldowns por tipo de alerta (segundos)
COOLDOWNS = {
    "ultimo_zap_geada":       900,
    "ultimo_zap_phoma":       10800,
    "ultimo_zap_ferrugem":    43200,
    "ultimo_zap_escaldadura": 1800,
    "ultimo_zap_offline":     3600,
}
for key in COOLDOWNS:
    if key not in st.session_state:
        st.session_state[key] = 0.0

# ============================================================
# 2. FUNÇÕES AUXILIARES
# ============================================================
def enviar_alerta_whatsapp(mensagem, chave_cooldown):
    """Envia alerta WhatsApp com cooldown individual por tipo de risco."""
    agora = time.time()
    if (agora - st.session_state[chave_cooldown]) < COOLDOWNS[chave_cooldown]:
        return
    telefone = "%2B5512996005169"
    api_key  = "7714077"
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={telefone}"
        f"&text={urllib.parse.quote(mensagem)}"
        f"&apikey={api_key}"
    )
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            st.session_state[chave_cooldown] = agora
            st.sidebar.success("✅ Alerta WhatsApp enviado!")
        else:
            st.sidebar.warning(f"⚠️ CallMeBot retornou HTTP {res.status_code}")
    except Exception:
        st.sidebar.error("❌ Erro ao disparar alerta WhatsApp")


def calcular_ponto_orvalho(T, RH):
    """Ponto de Orvalho — Magnus-Tetens. max(RH, 0.01) evita log(0)."""
    b, c  = 17.67, 243.5
    gamma = (b * T / (c + T)) + np.log(max(RH, 0.01) / 100.0)
    return round((c * gamma) / (b - gamma), 1)


def calcular_sensacao_termica(T, RH):
    """Heat Index simplificado — válido acima de 20°C."""
    if T < 20:
        return round(T, 1)
    hi = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    return round(hi, 1)

# ============================================================
# 3. QUERIES AO BANCO
# ============================================================
@st.cache_data(ttl=20)
def carregar_dados(d1, d2):
    """
    Retorna leituras do período filtrado.
    CORREÇÃO: usa query parametrizada (sem SQL injection).
    CORREÇÃO: trata timestamps com e sem timezone antes de normalizar para UTC naive.
    """
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        # Query parametrizada — sem f-string com datas
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
        # CORREÇÃO CRÍTICA: tz_convert lança TypeError se coluna for tz-naive
        # Verifica presença de timezone antes de converter
        if dt.dt.tz is not None:
            df["data_hora"] = dt.dt.tz_convert("UTC").dt.tz_localize(None)
        else:
            df["data_hora"] = dt  # Já naive — assume UTC (padrão do banco)

        return df
    except Exception as e:
        st.error(f"Erro de conexão com o banco: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def carregar_horas_frio():
    """
    Acúmulo de Horas de Frio nos últimos 90 dias — janela FIXA, independente do filtro.
    CORREÇÃO: não usa o df filtrado pelo usuário (que daria 0h se filtrar 'hoje').
    Conta horas DISTINTAS abaixo de 10°C para não multiplicar leituras por hora.
    Meta agronômica para florada uniforme do Arábica: ~200h acumuladas.
    """
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE_TRUNC('hour', data_hora)) AS horas_frio
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
    """
    Busca sensor_ids do banco — suporte dinâmico a múltiplos sensores.
    Novos ESP32 em campo aparecem automaticamente no filtro sem alterar o código.
    """
    try:
        conn   = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sensor_id FROM leituras_cafe ORDER BY sensor_id")
        rows = cursor.fetchall()
        conn.close()
        return ["Todos"] + [r[0] for r in rows]
    except Exception:
        return ["Todos", "ESP32_Fazenda"]  # Fallback se banco offline

# ============================================================
# 4. SISTEMA DE LOGIN
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

# --- BARRA LATERAL ---
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

# --- CARREGAMENTO E FILTRO ---
df_completo = carregar_dados(data_ini, data_fim)

if sensor_selecionado != "Todos" and not df_completo.empty:
    df = df_completo[df_completo["sensor_id"] == sensor_selecionado].copy()
else:
    df = df_completo.copy()

# --- CABEÇALHO ---
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
horas_frio = carregar_horas_frio()  # Janela fixa de 90 dias — independente do filtro

# Flags de risco agronômico
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
          help="Últimos 90 dias | Horas distintas abaixo de 10°C | Meta: 200h para florada uniforme do Arábica")

st.divider()

# ============================================================
# 8. ALERTAS AGRONÔMICOS
# ============================================================
st.subheader("🚨 Alertas de Campo")
algum_alerta = False

# --- Sensor Offline ---
# CORREÇÃO: datetime.now(timezone.utc) em vez de datetime.now() (hora local, UTC-3)
# Sem isso a diferença seria sempre -180 min e o sensor NUNCA aparecia offline
agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
diff_min  = max(0.0, (agora_utc - atual["data_hora"]).total_seconds() / 60)

if diff_min > 20:
    algum_alerta = True
    st.error(
        f"📡 **SENSOR OFFLINE** — Última leitura há {int(diff_min)} minutos. "
        "Verifique o ESP32 e a conexão Wi-Fi."
    )
    enviar_alerta_whatsapp(
        f"⚠️ ALERTA top1nfo: Sensor offline há {int(diff_min)} min. Verifique o ESP32!",
        "ultimo_zap_offline"
    )

# --- Geada de Baixada (≤ 4°C) ---
if risco_geada:
    algum_alerta = True
    st.error(
        f"❄️ **RISCO DE GEADA** — {T}°C detectado\n\n"
        "**Plano de Ação:** Mantenha as ruas limpas para escoamento do ar frio. "
        "Chegue terra no tronco das plantas novas. Evite irrigação noturna."
    )
    enviar_alerta_whatsapp(
        f"❄️ ALERTA GEADA top1nfo\nTemperatura: {T}°C\n\n"
        "Ação: Ruas limpas, terra no tronco das novas, sem irrigação noturna.",
        "ultimo_zap_geada"
    )

# --- Phoma (10°C–18°C + Umidade > 85%) ---
if risco_phoma:
    algum_alerta = True
    st.warning(
        f"🍄 **RISCO DE PHOMA** — {T}°C com {H}% de umidade\n\n"
        "**Plano de Ação:** Vistorie brotações novas nas próximas 48h. "
        "Lesões escuras nos ramos = aplique cúpricos. Priorize lavouras em encosta."
    )
    enviar_alerta_whatsapp(
        f"🍄 ALERTA PHOMA top1nfo\nT:{T}°C | U:{H}%\n\n"
        "Ação: Vistorie brotações 48h. Lesões escuras = cúpricos.",
        "ultimo_zap_phoma"
    )

# --- Ferrugem Tardia (18°C–24°C + Umidade > 90%) ---
if risco_ferrugem:
    algum_alerta = True
    st.warning(
        f"🟠 **RISCO DE FERRUGEM TARDIA** — {T}°C com {H}% de umidade\n\n"
        "**Plano de Ação:** Amostragem foliar em 20 plantas representativas. "
        "Se incidência > 5%, aplique fungicida sistêmico. Registre data e produto."
    )
    enviar_alerta_whatsapp(
        f"🟠 ALERTA FERRUGEM top1nfo\nT:{T}°C | U:{H}%\n\n"
        "Ação: Amostragem foliar. Se >5% aplique sistêmico.",
        "ultimo_zap_ferrugem"
    )

# --- Escaldadura (≥ 32°C) ---
if risco_escaldadura:
    algum_alerta = True
    st.warning(
        f"🔥 **RISCO DE ESCALDADURA** — {T}°C\n\n"
        "**Plano de Ação:** NÃO roçar a braquiária nas entrelinhas agora. "
        "Cobertura vegetal protege a raiz. Irrigação somente pela manhã."
    )
    enviar_alerta_whatsapp(
        f"🔥 ALERTA ESCALDADURA top1nfo\nT:{T}°C\n\n"
        "Ação: Não roce entrelinhas. Irrigação só pela manhã.",
        "ultimo_zap_escaldadura"
    )

if not algum_alerta:
    st.success("✅ Nenhum risco agronômico detectado. Lavoura em condições normais.")

st.divider()

# ============================================================
# 9. GRÁFICO PLOTLY
# ============================================================
col_g1, col_g2 = st.columns([3, 1])

with col_g1:
    st.markdown("### 📈 Evolução Climática")
    df_graf = df.sort_values("data_hora")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_graf["data_hora"],
        y=df_graf["temperatura"],
        name="Temperatura (°C)",
        line=dict(color="#E05C2A", width=2),
        mode="lines"
    ))

    fig.add_trace(go.Scatter(
        x=df_graf["data_hora"],
        y=df_graf["umidade"],
        name="Umidade (%)",
        line=dict(color="#2A7AE0", width=2, dash="dot"),
        mode="lines",
        yaxis="y2"
    ))

    # Linha de geada — referência visual permanente no gráfico
    fig.add_hline(
        y=4,
        line=dict(color="cyan", width=1.5, dash="dash"),
        annotation_text="⚠️ Limite de Geada (4°C)",
        annotation_position="bottom right",
        annotation_font_color="cyan"
    )

    # Linha de escaldadura
    fig.add_hline(
        y=32,
        line=dict(color="red", width=1.5, dash="dash"),
        annotation_text="🔥 Escaldadura (32°C)",
        annotation_position="top right",
        annotation_font_color="red"
    )

    fig.update_layout(
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Horário", gridcolor="#333"),
        yaxis=dict(title="Temperatura (°C)", side="left", gridcolor="#333"),
        yaxis2=dict(title="Umidade (%)", overlaying="y", side="right", gridcolor="#333"),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified"
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
    st.caption(f"{horas_frio}/{META_HORAS_FRIO}h ({int(progresso * 100)}%) — últimos 90 dias")

    # Botão único de download direto — sem duplo st.button
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📊 Baixar CSV",
        data=csv,
        file_name=f"top1nfo_{data_ini}_{data_fim}.csv",
        mime="text/csv",
        use_container_width=True
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
        use_container_width=True,
        hide_index=True
    )
