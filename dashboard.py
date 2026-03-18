import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time
import os
import numpy as np
from datetime import datetime, timedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="top1nfo - Inteligência Agro", layout="wide")

# Inicializa memória de alertas (Anti-Spam)
alertas_keys = ['ultimo_zap_calor', 'ultimo_zap_geada', 'ultimo_zap_fungo', 'ultimo_zap_offline']
for key in alertas_keys:
    if key not in st.session_state:
        st.session_state[key] = 0

# 2. FUNÇÕES DE SUPORTE
def enviar_alerta_whatsapp(mensagem):
    telefone = "%2B5512996005169"
    api_key = "7714077"
    msg_encoded = urllib.parse.quote(mensagem)
    url = f"https://api.callmebot.com/whatsapp.php?phone={telefone}&text={msg_encoded}&apikey={api_key}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            st.sidebar.success("✅ Alerta enviado ao WhatsApp")
    except:
        st.sidebar.error("❌ Erro ao disparar alerta")

def calcular_ponto_orvalho(T, RH):
    """Cálculo do Ponto de Orvalho usando a aproximação de Magnus-Tetens"""
    b, c = 17.67, 243.5
    gamma = (b * T / (c + T)) + np.log(RH / 100.0)
    return round((c * gamma) / (b - gamma), 1)

def calcular_sensacao_termica(T, RH):
    """Cálculo simplificado de Sensação Térmica / Heat Index"""
    if T < 20: return T # Não se aplica a frio extremo nesta fórmula
    hi = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    return round(hi, 1)

# 3. SISTEMA DE LOGIN
def verifica_senha():
    SENHA_CORRETA = "agrobit2026"
    if "senha_correta" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if os.path.exists("logo.jpg"): st.image("logo.jpg", use_container_width=True)
            st.markdown("### 🔒 Área Restrita - top1nfo")
            senha = st.text_input("Senha de Acesso:", type="password")
            if st.button("Entrar"):
                if senha == SENHA_CORRETA:
                    st.session_state["senha_correta"] = True
                    st.rerun()
                else: st.error("❌ Acesso negado.")
        return False
    return True

# 4. DASHBOARD PRINCIPAL
if verifica_senha():
    # BARRA LATERAL
    if os.path.exists("logo.jpg"): st.sidebar.image("logo.jpg", width=150)
    st.sidebar.header("🗓️ Filtros")
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    data_ini = st.sidebar.date_input("Data Inicial", ontem)
    data_fim = st.sidebar.date_input("Data Final", hoje)

    DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

    @st.cache_data(ttl=10)
    def carregar_dados(d1, d2):
        try:
            conn = psycopg2.connect(DB_URL)
            query = f"""
                SELECT data_hora, temperatura, umidade, sensor_id 
                FROM leituras_cafe 
                WHERE data_hora::date BETWEEN '{d1}' AND '{d2}'
                ORDER BY data_hora DESC LIMIT 3000
            """
            df = pd.read_sql(query, conn)
            conn.close()
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            return df
        except Exception as e:
            st.error(f"Erro de Conexão: {e}")
            return pd.DataFrame()

    df = carregar_dados(data_ini, data_fim)

    st.title("🚜 Painel de Inteligência Cafeeira")
    st.markdown("Monitoramento de precisão top1nfo para alta produtividade.")
    st.divider()

    if not df.empty:
        # --- PROCESSAMENTO DE DADOS ATUAIS ---
        atual = df.iloc[0]
        anterior = df.iloc[1] if len(df) > 1 else atual
        
        T, H = atual['temperatura'], atual['umidade']
        dT = round(T - anterior['temperatura'], 1)
        
        orvalho = calcular_ponto_orvalho(T, H)
        sensacao = calcular_sensacao_termica(T, H)
        
        # --- LÓGICA DE RISCOS ---
        risco_ferrugem = "BAIXO"
        cor_ferrugem = "normal"
        if 18 <= T <= 28 and H > 90:
            risco_ferrugem = "ALTO"
            cor_ferrugem = "inverse"

        # --- EXIBIÇÃO DE MÉTRICAS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temperatura", f"{T} °C", f"{dT} °C", delta_color="inverse")
        c2.metric("Umidade Relativa", f"{H} %")
        c3.metric("Ponto de Orvalho", f"{orvalho} °C", "Folha Seca" if T > orvalho + 2 else "Risco Orvalho")
        c4.metric("Risco de Ferrugem", risco_ferrugem, delta=risco_ferrugem, delta_color=cor_ferrugem)

        # --- SEÇÃO DE ALERTAS ATIVOS ---
        st.subheader("🚨 Alertas de Campo")
        t_agora = time.time()
        
        # Alerta Offline
        diff_offline = (pd.Timestamp.now().replace(tzinfo=None) - atual['data_hora'].replace(tzinfo=None)).total_seconds() / 60
        if diff_offline > 20:
            st.error(f"⚠️ SENSOR OFFLINE: Última leitura há {int(diff_offline)} min.")
            if (t_agora - st.session_state.ultimo_zap_offline) > 3600:
                enviar_alerta_whatsapp(f"ALERTA: Sensor top1nfo Offline ha {int(diff_offline)} min!")
                st.session_state.ultimo_zap_offline = t_agora

        # Alerta Calor / Frio / Fungo
        if T >= 33.0:
            st.warning(f"🔥 CALOR CRÍTICO: {T}°C (Risco de Escaldadura)")
            if (t_agora - st.session_state.ultimo_zap_calor) > 1800:
                enviar_alerta_whatsapp(f"ALERTA CALOR: {T}C na fazenda!")
                st.session_state.ultimo_zap_calor = t_agora
        
        if T <= 4.0:
            st.info(f"❄️ RISCO DE GEADA: {T}°C")
            if (t_agora - st.session_state.ultimo_zap_geada) > 900:
                enviar_alerta_whatsapp(f"ALERTA GEADA: {T}C detectado!")
                st.session_state.ultimo_zap_geada = t_agora

        if risco_ferrugem == "ALTO":
            st.warning("🍄 RISCO DE FUNGOS: Condição ideal para Ferrugem do Café.")
            if (t_agora - st.session_state.ultimo_zap_fungo) > 43200: # 12 horas
                enviar_alerta_whatsapp("ALERTA FUNGOS: Clima favoravel a ferrugem nas ultimas horas.")
                st.session_state.ultimo_zap_fungo = t_agora

        st.divider()

        # --- GRÁFICOS ---
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            st.markdown("### 📈 Evolução Climática")
            st.line_chart(df.set_index('data_hora')[['temperatura', 'umidade']])
        
        with col_g2:
            st.markdown("### 📋 Resumo do Período")
            st.write(f"**Máxima:** {df['temperatura'].max()} °C")
            st.write(f"**Mínima:** {df['temperatura'].min()} °C")
            st.write(f"**Sensação Atual:** {sensacao} °C")
            st.write(f"**Registros no banco:** {len(df)}")
            if st.button("📊 Baixar Relatório CSV"):
                df.to_csv("relatorio_top1nfo.csv", index=False)
                st.success("Download pronto!")

        with st.expander("🔍 Log de Auditoria"):
            st.dataframe(df, use_container_width=True)

        if st.sidebar.button("Logoff"):
            del st.session_state["senha_correta"]
            st.rerun()
    else:
        st.warning("Nenhum dado encontrado para as datas selecionadas.")
