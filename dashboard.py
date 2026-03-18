import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time

# 1. Configuração da Página
st.set_page_config(page_title="top1nfo - Área do Produtor", layout="wide")

# --- MEMÓRIA DO SISTEMA (Evita Spam no WhatsApp) ---
if 'ultimo_zap_calor' not in st.session_state: st.session_state.ultimo_zap_calor = 0
if 'ultimo_zap_geada' not in st.session_state: st.session_state.ultimo_zap_geada = 0
if 'ultimo_zap_fungo' not in st.session_state: st.session_state.ultimo_zap_fungo = 0

# --- FUNÇÃO DE DISPARO DO WHATSAPP (VERSÃO BLINDADA) ---
def enviar_alerta_whatsapp(texto_puro):
    telefone = "5512996005169"
    api_key = "7714077"
    
    # Substitui espaços por + para formato de URL seguro
    texto_url = texto_puro.replace(" ", "+")
    url = f"https://api.callmebot.com/whatsapp.php?phone={telefone}&text={texto_url}&apikey={api_key}"
    
    try:
        # Mostra o que está acontecendo na barra lateral para você auditar
        st.sidebar.info(f"Tentando enviar: {texto_puro}")
        
        resposta = requests.get(url, timeout=15)
        
        if resposta.status_code == 200:
            st.sidebar.success("✅ WhatsApp enviado com sucesso!")
        else:
            st.sidebar.error(f"❌ Erro na API ({resposta.status_code}): {resposta.text}")
    except Exception as e:
        st.sidebar.error(f"❌ Falha de conexão: {e}")

# --- SISTEMA DE LOGIN ---
def verifica_senha():
    SENHA_CORRETA = "agrobit2026"

    def senha_inserida():
        if st.session_state["senha"] == SENHA_CORRETA:
            st.session_state["senha_correta"] = True
            del st.session_state["senha"]
        else:
            st.session_state["senha_correta"] = False

    if "senha_correta" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try: st.image("logo.jpg", use_container_width=True)
            except: pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            st.text_input("Digite sua senha de Produtor:", type="password", on_change=senha_inserida, key="senha")
        return False
    elif not st.session_state["senha_correta"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try: st.image("logo.jpg", use_container_width=True)
            except: pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            st.text_input("Digite sua senha de Produtor:", type="password", on_change=senha_inserida, key="senha")
            st.error("❌ Senha incorreta. Acesso negado.")
        return False
    else:
        return True

# --- SE O LOGIN FOR SUCESSO ---
if verifica_senha():
    
    DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

    @st.cache_data(ttl=10)
    def carregar_dados():
        try:
            conn = psycopg2.connect(DB_URL)
            query = "SELECT data_hora, temperatura, umidade FROM leituras_cafe ORDER BY data_hora DESC LIMIT 500"
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"Erro ao conectar no banco: {e}")
            return pd.DataFrame()

    # Cabeçalho Interno
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        try: st.image("logo.jpg", use_container_width=True)
        except: st.write("*(Logo top1nfo)*")

    with col_titulo:
        st.title("Painel da Fazenda")
        st.markdown("**Bem-vindo, Produtor!** | Monitoramento em Tempo Real")
    st.divider()

    df = carregar_dados()

    if not df.empty:
        ultima_temp = df['temperatura'].iloc[0]
        ultima_umi = df['umidade'].iloc[0]
        
        temp_anterior = df['temperatura'].iloc[1] if len(df) > 1 else ultima_temp
        umi_anterior = df['umidade'].iloc[1] if len(df) > 1 else ultima_umi

        media_temp = round(df['temperatura'].mean(), 1)
        media_umi = round(df['umidade'].mean(), 1)

        # --- SISTEMA DE ALERTAS INTELIGENTES ---
        tempo_atual = time.time()

        # 1. Alerta de Calor Extremo (Reforçado para WhatsApp)
        if ultima_temp >= 33.0:
            st.error(f"🚨 ALERTA CRÍTICO: Temperatura atingiu {ultima_temp}°C!")
            # Envia a cada 30 minutos (1800 segundos)
            if (tempo_atual - st.session_state.ultimo_zap_calor) > 1800:
                enviar_alerta_whatsapp(f"ALERTA CRITICO: Temperatura de {ultima_temp}C detectada. Risco para o grao!")
                st.session_state.ultimo_zap_calor = tempo_atual

        # 2. Alerta de Geada (Frio letal)
        elif ultima_temp <= 4.0:
            st.error(f"❄️ ALERTA GEADA: Temperatura caiu para {ultima_temp}°C!")
            # Envia a cada 15 minutos (900 segundos)
            if (tempo_atual - st.session_state.ultimo_zap_geada) > 900:
                enviar_alerta_whatsapp(f"ALERTA GEADA: Temperatura caiu para {ultima_temp}C! Proteja a plantacao.")
                st.session_state.ultimo_zap_geada = tempo_atual

        # 3. Risco de Fungos (Umidade alta + Temperatura morna)
        elif ultima_umi > 90.0 and (20.0 <= ultima_temp <= 25.0):
            st.warning(f"🍄 ALERTA FUNGOS: Clima favorável para ferrugem.")
            # Envia a cada 12 horas (43200 segundos)
            if (tempo_atual - st.session_state.ultimo_zap_fungo) > 43200:
                enviar_alerta_whatsapp(f"ALERTA FUNGOS: Umidade {ultima_umi}% e Temp {ultima_temp}C. Risco de ferrugem.")
                st.session_state.ultimo_zap_fungo = tempo_atual

        # Outros Alertas de Atenção (Apenas Visual)
        elif ultima_temp >= 28:
            st.warning(f"⚠️ ATENÇÃO: Temperatura subindo ({ultima_temp}°C).")
        else:
            st.success(f"✅ Condições seguras ({ultima_temp}°C).")

        # Indicadores
        st.markdown("### 📊 Indicadores Atuais")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="Temperatura", value=f"{ultima_temp} °C", delta=f"{round(ultima_temp - temp_anterior, 1)} °C", delta_color="inverse") 
        col2.metric(label="Umidade", value=f"{ultima_umi} %", delta=f"{round(ultima_umi - umi_anterior, 1)} %")
        col3.metric(label="Média Temp.", value=f"{media_temp} °C")
        col4.metric(label="Média Umi.", value=f"{media_umi} %")

        st.divider()

        st.markdown("### 📈 Histórico Climático")
        df_grafico = df.set_index('data_hora') 
        st.line_chart(df_grafico[['temperatura', 'umidade']])

        with st.expander("🔍 Ver Auditoria de Dados (Log Bruto)"):
            st.dataframe(df.head(20))
            
        if st.button("Sair do Sistema"):
            del st.session_state["senha_correta"]
            st.rerun()
            
    else:
        st.warning("Aguardando transmissão dos sensores top1nfo...")
