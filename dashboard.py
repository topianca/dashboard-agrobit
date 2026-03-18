import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time
from datetime import datetime, timedelta

# 1. Configuração da Página
st.set_page_config(page_title="top1nfo - Área do Produtor", layout="wide")

# --- MEMÓRIA DO SISTEMA (Anti-Spam) ---
if 'ultimo_zap_calor' not in st.session_state: st.session_state.ultimo_zap_calor = 0
if 'ultimo_zap_geada' not in st.session_state: st.session_state.ultimo_zap_geada = 0
if 'ultimo_zap_fungo' not in st.session_state: st.session_state.ultimo_zap_fungo = 0
if 'ultimo_zap_offline' not in st.session_state: st.session_state.ultimo_zap_offline = 0

# --- FUNÇÃO DE DISPARO DO WHATSAPP ---
def enviar_alerta_whatsapp(texto_puro):
    telefone = "%2B5512996005169" # Formato internacional com + (codificado como %2B)
    api_key = "7714077"
    texto_url = texto_puro.replace(" ", "+")
    url = f"https://api.callmebot.com/whatsapp.php?phone={telefone}&text={texto_url}&apikey={api_key}"
    
    try:
        st.sidebar.info(f"Enviando: {texto_puro}")
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            st.sidebar.success("✅ WhatsApp enviado!")
        else:
            st.sidebar.error(f"❌ Erro API: {res.status_code}")
    except Exception as e:
        st.sidebar.error(f"❌ Falha Conexão: {e}")

# --- SISTEMA DE LOGIN ---
def verifica_senha():
    SENHA_CORRETA = "agrobit2026"
    if "senha_correta" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try: st.image("logo.jpg", use_container_width=True)
            except: pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            senha = st.text_input("Digite sua senha de Produtor:", type="password")
            if st.button("Entrar"):
                if senha == SENHA_CORRETA:
                    st.session_state["senha_correta"] = True
                    st.rerun()
                else: st.error("❌ Senha incorreta.")
        return False
    return True

# --- INÍCIO DO SISTEMA ---
if verifica_senha():
    
    # --- BARRA LATERAL: FILTROS DE DATA ---
    st.sidebar.header("🗓️ Filtros Históricos")
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    
    data_inicio = st.sidebar.date_input("Data de Início", ontem)
    data_fim = st.sidebar.date_input("Data de Fim", hoje)

    DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

    @st.cache_data(ttl=10)
    def carregar_dados(d_inicio, d_fim):
        try:
            conn = psycopg2.connect(DB_URL)
            # Query agora filtra pelo intervalo de datas escolhido
            query = f"""
                SELECT data_hora, temperatura, umidade 
                FROM leituras_cafe 
                WHERE data_hora::date >= '{d_inicio}' AND data_hora::date <= '{d_fim}'
                ORDER BY data_hora DESC
            """
            df = pd.read_sql(query, conn)
            conn.close()
            # Garante que data_hora é um formato de tempo do pandas
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            return df
        except Exception as e:
            st.error(f"Erro ao conectar no banco: {e}")
            return pd.DataFrame()

    # Cabeçalho
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        try: st.image("logo.jpg", use_container_width=True)
        except: st.write("*(Logo top1nfo)*")
    with col_titulo:
        st.title("Painel da Fazenda")
        st.markdown(f"Exibindo dados de **{data_inicio}** até **{data_fim}**")
    st.divider()

    df = carregar_dados(data_inicio, data_fim)

    if not df.empty:
        # --- LÓGICA WATCHDOG: SENSOR OFFLINE ---
        ultima_leitura = df['data_hora'].iloc[0]
        agora = datetime.now()
        # Calcula diferença em minutos (ajuste se o banco estiver em UTC)
        diff_tempo = (agora - ultima_leitura.replace(tzinfo=None)).total_seconds() / 60
        
        if diff_tempo > 15: # 15 minutos sem dados
            st.warning(f"⚠️ ATENÇÃO: Sensor possivelmente OFFLINE. Última leitura há {int(diff_tempo)} min.")
            if (time.time() - st.session_state.ultimo_zap_offline) > 3600: # Alerta a cada 1 hora
                enviar_alerta_whatsapp(f"ALERTA: Sensor top1nfo Offline ha {int(diff_tempo)} minutos! Verifique a conexao.")
                st.session_state.ultimo_zap_offline = time.time()

        # Dados Atuais
        ultima_temp = df['temperatura'].iloc[0]
        ultima_umi = df['umidade'].iloc[0]
        temp_anterior = df['temperatura'].iloc[1] if len(df) > 1 else ultima_temp
        media_temp = round(df['temperatura'].mean(), 1)
        media_umi = round(df['umidade'].mean(), 1)

        # --- ALERTAS DE CLIMA ---
        tempo_atual = time.time()
        if ultima_temp >= 33.0:
            st.error(f"🚨 ALERTA CRÍTICO: Temperatura atingiu {ultima_temp}°C!")
            if (tempo_atual - st.session_state.ultimo_zap_calor) > 1800:
                enviar_alerta_whatsapp(f"ALERTA CRITICO: Temperatura de {ultima_temp}C detectada!")
                st.session_state.ultimo_zap_calor = tempo_atual
        elif ultima_temp <= 4.0:
            st.error(f"❄️ ALERTA GEADA: Temperatura caiu para {ultima_temp}°C!")
            if (tempo_atual - st.session_state.ultimo_zap_geada) > 900:
                enviar_alerta_whatsapp(f"ALERTA GEADA: Temperatura de {ultima_temp}C detectada!")
                st.session_state.ultimo_zap_geada = tempo_atual

        # Indicadores
        st.markdown("### 📊 Indicadores do Período")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Temperatura", f"{ultima_temp} °C", f"{round(ultima_temp - temp_anterior, 1)} °C", delta_color="inverse")
        col2.metric("Umidade", f"{ultima_umi} %")
        col3.metric("Média Temp.", f"{media_temp} °C")
        col4.metric("Média Umi.", f"{media_umi} %")

        st.divider()

        # Gráfico Histórico
        st.markdown("### 📈 Evolução Climática")
        st.line_chart(df.set_index('data_hora')[['temperatura', 'umidade']])

        with st.expander("🔍 Log de Auditoria"):
            st.dataframe(df.head(50))
            
        if st.sidebar.button("Sair do Sistema"):
            del st.session_state["senha_correta"]
            st.rerun()
    else:
        st.warning(f"Sem dados encontrados para o período de {data_inicio} a {data_fim}.")
