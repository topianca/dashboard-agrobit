import streamlit as st
import pandas as pd
import psycopg2

# 1. Configuração da Página
st.set_page_config(page_title="top1nfo - Área do Produtor", layout="wide")

# --- SISTEMA DE LOGIN (A PORTA DE ENTRADA) ---
def verifica_senha():
    """Retorna True se o usuário digitar a senha correta."""
    # A senha do nosso primeiro cliente (pode ser o seu sogro!)
    SENHA_CORRETA = "agrobit2026"

    def senha_inserida():
        if st.session_state["senha"] == SENHA_CORRETA:
            st.session_state["senha_correta"] = True
            del st.session_state["senha"]  # Apaga da memória por segurança
        else:
            st.session_state["senha_correta"] = False

    if "senha_correta" not in st.session_state:
        # Tela inicial (Fechada)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try:
                st.image("logo.jpg", use_container_width=True)
            except:
                pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            st.text_input("Digite sua senha de Produtor:", type="password", on_change=senha_inserida, key="senha")
        return False
    elif not st.session_state["senha_correta"]:
        # Senha errada
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try:
                st.image("logo.jpg", use_container_width=True)
            except:
                pass
            st.markdown("### 🔒 Acesso Restrito - top1nfo")
            st.text_input("Digite sua senha de Produtor:", type="password", on_change=senha_inserida, key="senha")
            st.error("❌ Senha incorreta. Acesso negado.")
        return False
    else:
        # Passou!
        return True

# --- SE O LOGIN FOR SUCESSO, MOSTRA O SISTEMA ---
if verifica_senha():
    
    # 2. Credenciais do Banco na Nuvem
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
        try:
            st.image("logo.jpg", use_container_width=True)
        except:
            st.write("*(Logo top1nfo)*")

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

        # Alertas Inteligentes
        if ultima_temp >= 30:
            st.error(f"🚨 ALERTA CRÍTICO: Temperatura atingiu {ultima_temp}°C! Risco de perda de qualidade no grão.")
        elif ultima_temp >= 28:
            st.warning(f"⚠️ ATENÇÃO: Temperatura subindo ({ultima_temp}°C). Monitore a secagem de perto.")
        else:
            st.success(f"✅ Clima favorável. Temperatura em condições seguras ({ultima_temp}°C).")

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
            
        # Botão de Sair (Logout)
        if st.button("Sair do Sistema"):
            del st.session_state["senha_correta"]
            st.rerun()
            
    else:
        st.warning("Aguardando transmissão dos sensores top1nfo...")
