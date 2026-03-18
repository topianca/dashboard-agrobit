import streamlit as st
import pandas as pd
import psycopg2
import requests
import urllib.parse
import time
from datetime import datetime, timedelta

# ==========================================
# 1. CONFIGURAÇÃO E MEMÓRIA DO SISTEMA
# ==========================================
st.set_page_config(page_title="top1nfo - Área do Produtor", layout="wide")

# Inicializa as variáveis de controle de envio (Anti-Spam)
for alerta in ['ultimo_zap_calor', 'ultimo_zap_geada', 'ultimo_zap_fungo', 'ultimo_zap_offline']:
    if alerta not in st.session_state:
        st.session_state[alerta] = 0

# ==========================================
# 2. FUNÇÕES DE COMUNICAÇÃO (WHATSAPP)
# ==========================================
def enviar_alerta_whatsapp(mensagem_pura):
    """Envia alerta via CallMeBot com tratamento de caracteres especiais."""
    telefone = "%2B5512996005169" # Formato +55...
    api_key = "7714077"
    
    # Codifica a mensagem para formato de URL (resolve espaços, emojis e acentos)
    msg_encoded = urllib.parse.quote(mensagem_pura)
    url = f"https://api.callmebot.com/whatsapp.php?phone={telefone}&text={msg_encoded}&apikey={api_key}"
    
    try:
        # Log visual na barra lateral para o produtor saber que o envio foi tentado
        st.sidebar.info(f"📤 Tentando enviar WhatsApp...")
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            st.sidebar.success("✅ Alerta entregue ao WhatsApp!")
        else:
            st.sidebar.error(f"❌ Erro na API CallMeBot: {res.status_code}")
    except Exception as e:
        st.sidebar.error(f"❌ Falha de conexão: {e}")

# ==========================================
# 3. CONTROLE DE ACESSO (LOGIN)
# ==========================================
def verifica_senha():
    """Valida o acesso do produtor."""
    SENHA_CORRETA = "agrobit2026"
    
    if "senha_correta" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try: st.image("logo.jpg", use_container_width=True)
            except: pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            senha = st.text_input("Senha do Produtor:", type="password")
            if st.button("Acessar Painel"):
                if senha == SENHA_CORRETA:
                    st.session_state["senha_correta"] = True
                    st.rerun()
                else: st.error("❌ Senha incorreta.")
        return False
    return True

# ==========================================
# 4. EXECUÇÃO DO PAINEL (APÓS LOGIN)
# ==========================================
if verifica_senha():
    
    # --- BARRA LATERAL: CONFIGURAÇÕES ---
    st.sidebar.image("logo.jpg", width=150) if "logo.jpg" else None
    st.sidebar.header("🗓️ Filtro de Período")
    
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    data_inicio = st.sidebar.date_input("Início", ontem)
    data_fim = st.sidebar.date_input("Fim", hoje)

    # --- CONEXÃO COM O BANCO ---
    DB_URL = "postgresql://postgres:wQsuidbkKmMEmLCpNPuCwQCvdsUAdCUl@ballast.proxy.rlwy.net:56019/railway"

    @st.cache_data(ttl=10)
    def carregar_dados(d_ini, d_fim):
        try:
            conn = psycopg2.connect(DB_URL)
            # Busca dados garantindo o fuso horário e limites saudáveis
            query = f"""
                SELECT data_hora, temperatura, umidade, sensor_id
                FROM leituras_cafe 
                WHERE data_hora::date BETWEEN '{d_ini}' AND '{d_ini}'
                OR (data_hora::date >= '{d_ini}' AND data_hora::date <= '{d_fim}')
                ORDER BY data_hora DESC 
                LIMIT 2000
            """
            df = pd.read_sql(query, conn)
            conn.close()
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            return df
        except Exception as e:
            st.error(f"Erro ao conectar no banco: {e}")
            return pd.DataFrame()

    # --- INTERFACE PRINCIPAL ---
    st.title("🚜 Painel da Fazenda Piloto")
    st.markdown(f"Monitoramento top1nfo | Dados de **{data_inicio.strftime('%d/%m/%Y')}** a **{data_fim.strftime('%d/%m/%Y')}**")
    st.divider()

    df = carregar_dados(data_inicio, data_fim)

    if not df.empty:
        # A) LÓGICA WATCHDOG (SENSOR OFFLINE)
        ultima_leitura = df['data_hora'].iloc[0]
        agora = pd.Timestamp.now()
        # Compara removendo informações de fuso para evitar erros de cálculo
        diff_minutos = (agora.replace(tzinfo=None) - ultima_leitura.replace(tzinfo=None)).total_seconds() / 60
        
        if diff_minutos > 15:
            st.warning(f"⚠️ **SENSOR OFFLINE:** Sem sinal há {int(diff_minutos)} minutos.")
            if (time.time() - st.session_state.ultimo_zap_offline) > 3600:
                enviar_alerta_whatsapp(f"🚨 ALERTA: Sensor top1nfo Offline na Fazenda ha {int(diff_minutos)} minutos!")
                st.session_state.ultimo_zap_offline = time.time()

        # B) INDICADORES ATUAIS
        ultima_temp = df['temperatura'].iloc[0]
        ultima_umi = df['umidade'].iloc[0]
        temp_anterior = df['temperatura'].iloc[1] if len(df) > 1 else ultima_temp
        media_temp = round(df['temperatura'].mean(), 1)
        media_umi = round(df['umidade'].mean(), 1)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Temperatura", f"{ultima_temp} °C", f"{round(ultima_temp - temp_anterior, 1)} °C", delta_color="inverse")
        col2.metric("Umidade", f"{ultima_umi} %")
        col3.metric("Média Temp.", f"{media_temp} °C")
        col4.metric("Média Umi.", f"{media_umi} %")

        # C) ALERTAS DE CLIMA
        tempo_atual = time.time()
        
        # Calor Crítico
        if ultima_temp >= 33.0:
            st.error(f"🔥 **ALERTA CALOR:** Temperatura crítica de {ultima_temp}°C!")
            if (tempo_atual - st.session_state.ultimo_zap_calor) > 1800:
                enviar_alerta_whatsapp(f"🚨 ALERTA CALOR: Temperatura de {ultima_temp}C na Fazenda!")
                st.session_state.ultimo_zap_calor = tempo_atual
        
        # Risco de Geada
        elif ultima_temp <= 4.0:
            st.error(f"❄️ **ALERTA GEADA:** Temperatura em {ultima_temp}°C!")
            if (tempo_atual - st.session_state.ultimo_zap_geada) > 900:
                enviar_alerta_whatsapp(f"❄️ ALERTA GEADA: Temperatura caiu para {ultima_temp}C!")
                st.session_state.ultimo_zap_geada = tempo_atual
        
        # Risco de Fungos
        elif ultima_umi > 90.0 and (20.0 <= ultima_temp <= 25.0):
            st.warning("🍄 **RISCO DE FUNGOS:** Clima favorável para ferrugem.")
            if (tempo_atual - st.session_state.ultimo_zap_fungo) > 43200: # 12 horas
                enviar_alerta_whatsapp(f"🍄 ALERTA FUNGOS: Umidade alta ({ultima_umi}%) e calor moderado. Risco de ferrugem!")
                st.session_state.ultimo_zap_fungo = tempo_atual

        st.divider()

        # D) GRÁFICO E HISTÓRICO
        st.markdown("### 📈 Evolução Climática")
        st.line_chart(df.set_index('data_hora')[['temperatura', 'umidade']])

        with st.expander(f"🔍 Auditoria de Dados ({len(df)} registros selecionados)"):
            st.dataframe(df, use_container_width=True)
            
        # Botão de Sair
        if st.sidebar.button("Logoff do Sistema"):
            del st.session_state["senha_correta"]
            st.rerun()

    else:
        st.warning("Nenhum registro encontrado para este período.")
        st.info("Dica: Verifique se o Worker e o Wokwi estão enviando dados.")
