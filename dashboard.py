import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time
import os
from datetime import datetime, timedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="top1nfo - Inteligência Cafeeira", layout="wide")

# Inicializa memória de alertas (Anti-Spam)
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
            st.sidebar.success("✅ Zap enviado!")
    except:
        st.sidebar.error("❌ Falha no Zap")

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
            if st.button("Entrar no Painel"):
                if senha == SENHA_CORRETA:
                    st.session_state["senha_correta"] = True
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta.")
        return False
    return True

# 4. PAINEL PRINCIPAL
if verifica_senha():
    
    # --- BARRA LATERAL ---
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

    # --- CABEÇALHO ---
    st.title("🚜 Inteligência Agronômica - Fazenda Piloto")
    st.markdown(f"Monitoramento top1nfo focado em produtividade cafeeira.")
    st.divider()

    df = carregar_dados(data_inicio, data_fim)

    if not df.empty:
        # A) WATCHDOG (SENSOR OFFLINE)
        u_leitura = df['data_hora'].iloc[0]
        agora = pd.Timestamp.now()
        diff_min = (agora.replace(tzinfo=None) - u_leitura.replace(tzinfo=None)).total_seconds() / 60
        
        if diff_min > 20:
            st.warning(f"⚠️ **SENSOR OFFLINE:** Sem sinal há {int(diff_min)} min. Verifique a bateria/WiFi.")
            if (time.time() - st.session_state.ultimo_zap_offline) > 3600:
                enviar_alerta_whatsapp(f"🚨 Sensor top1nfo Offline na Fazenda ha {int(diff_min)} minutos!")
                st.session_state.ultimo_zap_offline = time.time()

        # B) LÓGICA AGRONÔMICA (DADOS ATUAIS)
        u_temp = df['temperatura'].iloc[0]
        u_umi = df['umidade'].iloc[0]
        t_ant = df['temperatura'].iloc[1] if len(df) > 1 else u_temp

        # Cálculo do Ponto de Orvalho (Fórmula Simplificada)
        p_orvalho = round(u_temp - ((100 - u_umi) / 5), 1)

        # Cálculo de Risco de Ferrugem (Window: 18-28°C + Umi > 90%)
        risco_ferrugem = "BAIXO"
        cor_metric = "normal"
        if 18 <= u_temp <= 28 and u_umi > 90:
            risco_ferrugem = "ALTO"
            cor_metric = "inverse" # Vermelho no metric

        # C) INDICADORES VISUAIS
        st.subheader("📊 Condições de Campo")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temperatura", f"{u_temp} °C", f"{round(u_temp - t_ant, 1)} °C", delta_color="inverse")
        c2.metric("Umidade do Ar", f"{u_umi} %")
        c3.metric("Risco Ferrugem", risco_ferrugem, delta="Monitorar" if risco_ferrugem == "ALTO" else "Estável", delta_color=cor_metric)
        c4.metric("Ponto Orvalho", f"{p_orvalho} °C")

        # D) ALERTAS CRÍTICOS (WHATSAPP)
        t_atual = time.time()
        # Calor (Escaldadura)
        if u_temp >= 33.0 and (t_atual - st.session_state.ultimo_zap_calor) > 1800:
            enviar_alerta_whatsapp(f"🚨 ALERTA ESCALDADURA: {u_temp}C detectado. Risco ao fruto do cafe!")
            st.session_state.ultimo_zap_calor = t_atual
        # Geada
        elif u_temp <= 4.0 and (t_atual - st.session_state.ultimo_zap_geada) > 900:
            enviar_alerta_whatsapp(f"❄️ ALERTA GEADA: Temperatura caiu para {u_temp}C!")
            st.session_state.ultimo_zap_geada = t_atual
        # Ferrugem (Novo Alerta)
        elif risco_ferrugem == "ALTO" and (t_atual - st.session_state.ultimo_zap_fungo) > 43200: # 12h
            enviar_alerta_whatsapp(f"🍄 ALERTA FUNGOS: Clima favoravel para Ferrugem ({u_temp}C, {u_umi}%).")
            st.session_state.ultimo_zap_fungo = t_atual

        st.divider()

        # E) GRÁFICOS E AUDITORIA
        col_graf, col_info = st.columns([3, 1])
        with col_graf:
            st.markdown("### 📈 Histórico Climático")
            st.line_chart(df.set_index('data_hora')[['temperatura', 'umidade']])
        
        with col_info:
            st.markdown("### 📝 Resumo")
            st.write(f"**Máxima:** {df['temperatura'].max()} °C")
            st.write(f"**Mínima:** {df['temperatura'].min()} °C")
            st.write(f"**Média Umi:** {round(df['umidade'].mean(), 1)} %")
            if st.button("📥 Exportar CSV"):
                df.to_csv("dados_fazenda.csv", index=False)
                st.success("Arquivo gerado!")

        with st.expander(f"🔍 Auditoria Completa ({len(df)} registros)"):
            st.dataframe(df, use_container_width=True)
            
        if st.sidebar.button("Sair (Logoff)"):
            del st.session_state["senha_correta"]
            st.rerun()
    else:
        st.warning(f"Sem dados para o período de {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}.")
