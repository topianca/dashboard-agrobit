import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time
import os  # Adicionado para checar se o arquivo da logo existe
from datetime import datetime, timedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="top1nfo - Área do Produtor", layout="wide")

# Inicializa memória de alertas
for alerta in ['ultimo_zap_calor', 'ultimo_zap_geada', 'ultimo_zap_fungo', 'ultimo_zap_offline']:
    if alerta not in st.session_state:
        st.session_state[alerta] = 0

# 2. FUNÇÃO WHATSAPP
def enviar_alerta_whatsapp(mensagem_pura):
    telefone = "%2B5512996005169"
    api_key = "7714077"
    msg_encoded = urllib.parse.quote(mensagem_pura)
    url = f"https://api.callmebot.com/whatsapp.php?phone={telefone}&text={msg_encoded}&apikey={api_key}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            st.sidebar.success("✅ Alerta enviado!")
    except:
        st.sidebar.error("❌ Falha ao enviar Zap")

# 3. SISTEMA DE LOGIN
def verifica_senha():
    SENHA_CORRETA = "agrobit2026"
    if "senha_correta" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if os.path.exists("logo.jpg"):
                st.image("logo.jpg", use_container_width=True)
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            senha = st.text_input("Senha do Produtor:", type="password")
            if st.button("Acessar Painel"):
                if senha == SENHA_CORRETA:
                    st.session_state["senha_correta"] = True
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta.")
        return False
    return True

# 4. PAINEL PRINCIPAL
if verifica_senha():
    
    # Barra Lateral
    if os.path.exists("logo.jpg"):
        st.sidebar.image("logo.jpg", width=150)
    
    st.sidebar.header("🗓️ Filtro de Período")
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    data_inicio = st.sidebar.date_input("Início", ontem)
    data_fim = st.sidebar.date_input("Fim", hoje)

    DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

    @st.cache_data(ttl=10)
    def carregar_dados(d_ini, d_fim):
        try:
            conn = psycopg2.connect(DB_URL)
            query = f"""
                SELECT data_hora, temperatura, umidade, sensor_id
                FROM leituras_cafe 
                WHERE data_hora::date BETWEEN '{d_ini}' AND '{d_fim}'
                ORDER BY data_hora DESC 
                LIMIT 2000
            """
            df = pd.read_sql(query, conn)
            conn.close()
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            return df
        except Exception as e:
            st.error(f"Erro no banco: {e}")
            return pd.DataFrame()

    st.title("🚜 Painel da Fazenda Piloto")
    st.markdown(f"Monitoramento top1nfo | Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
    st.divider()

    df = carregar_dados(data_inicio, data_fim)

    if not df.empty:
        # WATCHDOG
        ultima_leitura = df['data_hora'].iloc[0]
        agora = pd.Timestamp.now()
        diff_min = (agora.replace(tzinfo=None) - ultima_leitura.replace(tzinfo=None)).total_seconds() / 60
        
        if diff_min > 15:
            st.warning(f"⚠️ **SENSOR OFFLINE:** Último sinal há {int(diff_min)} min.")
            if (time.time() - st.session_state.ultimo_zap_offline) > 3600:
                enviar_alerta_whatsapp(f"🚨 Sensor Offline ha {int(diff_min)} minutos!")
                st.session_state.ultimo_zap_offline = time.time()

        # INDICADORES
        u_temp = df['temperatura'].iloc[0]
        u_umi = df['umidade'].iloc[0]
        t_ant = df['temperatura'].iloc[1] if len(df) > 1 else u_temp

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temperatura", f"{u_temp} °C", f"{round(u_temp - t_ant, 1)} °C", delta_color="inverse")
        c2.metric("Umidade", f"{u_umi} %")
        c3.metric("Média Temp.", f"{round(df['temperatura'].mean(), 1)} °C")
        c4.metric("Média Umi.", f"{round(df['umidade'].mean(), 1)} %")

        # ALERTAS ZAP
        t_atual = time.time()
        if u_temp >= 33.0 and (t_atual - st.session_state.ultimo_zap_calor) > 1800:
            enviar_alerta_whatsapp(f"🚨 ALERTA CALOR: {u_temp}C na Fazenda!")
            st.session_state.ultimo_zap_calor = t_atual
        
        elif u_temp <= 4.0 and (t_atual - st.session_state.ultimo_zap_geada) > 900:
            enviar_alerta_whatsapp(f"❄️ ALERTA GEADA: {u_temp}C!")
            st.session_state.ultimo_zap_geada = t_atual

        st.divider()
        st.markdown("### 📈 Evolução Climática")
        st.line_chart(df.set_index('data_hora')[['temperatura', 'umidade']])

        with st.expander(f"🔍 Auditoria ({len(df)} registros)"):
            st.dataframe(df, use_container_width=True)
            
        if st.sidebar.button("Logoff"):
            del st.session_state["senha_correta"]
            st.rerun()
    else:
        st.warning("Sem dados para este período.")
