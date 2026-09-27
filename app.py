import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsbombpy import sb
from mplsoccer import Pitch

# Configuração inicial da página
st.set_page_config(page_title="Dashboard StatsBomb", layout="wide")

# ==========================================
# 1. GERENCIAMENTO DE ESTADO DA SESSÃO (SESSION STATE)
# ==========================================
# Inicializa variáveis na sessão do usuário se ainda não existirem
if 'jogador_comparador_a' not in st.session_state:
    st.session_state['jogador_comparador_a'] = None

if 'jogador_comparador_b' not in st.session_state:
    st.session_state['jogador_comparador_b'] = None

if 'filtros_aplicados' not in st.session_state:
    st.session_state['filtros_aplicados'] = False

# ==========================================
# 2. FUNÇÕES COM CACHE OTIMIZADO
# ==========================================
# O ttl=3600 armazena o resultado em memória por 1 hora, acelerando as requisições
@st.cache_data(ttl=3600)
def carregar_competicoes():
    return sb.competitions()

@st.cache_data(ttl=3600)
def carregar_partidas(competition_id, season_id):
    return sb.matches(competition_id=competition_id, season_id=season_id)

@st.cache_data(ttl=3600)
def carregar_eventos(match_id):
    return sb.events(match_id=match_id)

# ==========================================
# 3. FUNÇÕES DE VISUALIZAÇÃO
# ==========================================
def gerar_mapa_passes_chutes(df_eventos, time_selecionado, jogador_selecionado, min_minuto, max_minuto, qtd_max, mostrar_passes, mostrar_chutes):
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#1b2421', line_color='#c7d5cc')
    fig, ax = pitch.draw(figsize=(8, 5))
    
    # Aplicação dos Filtros
    df_filtrado = df_eventos[
        (df_eventos['team'] == time_selecionado) & 
        (df_eventos['minute'] >= min_minuto) & 
        (df_eventos['minute'] <= max_minuto)
    ].copy()
    
    if jogador_selecionado and jogador_selecionado != "Todos os Jogadores":
        df_filtrado = df_filtrado[df_filtrado['player'] == jogador_selecionado]

    # Limitador da quantidade de eventos
    df_filtrado = df_filtrado.head(qtd_max)

    # 1. Passes
    if mostrar_passes:
        df_passes = df_filtrado[df_filtrado['type'] == 'Pass']
        for _, pass_row in df_passes.iterrows():
            if 'location' in pass_row and isinstance(pass_row['location'], list):
                x1, y1 = pass_row['location'][0], pass_row['location'][1]
                x2, y2 = pass_row['pass_end_location'][0], pass_row['pass_end_location'][1]
                cor = '#2ecc71' if pd.isna(pass_row.get('pass_outcome')) else '#e74c3c'
                pitch.arrows(x1, y1, x2, y2, color=cor, alpha=0.6, ax=ax, width=1, headwidth=3)

    # 2. Chutes
    if mostrar_chutes:
        df_chutes = df_filtrado[df_filtrado['type'] == 'Shot']
        for _, shot_row in df_chutes.iterrows():
            if 'location' in shot_row and isinstance(shot_row['location'], list):
                x, y = shot_row['location'][0], shot_row['location'][1]
                is_gol = shot_row.get('shot_outcome') == 'Goal'
                cor = '#f1c40f' if is_gol else '#3498db'
                tamanho = 150 if is_gol else 70
                pitch.scatter(x, y, s=tamanho, color=cor, edgecolors='black', ax=ax, zorder=3)

    ax.set_title(f"Ações: {time_selecionado} ({min_minuto}' - {max_minuto}')", fontsize=11, color='white')
    return fig

def gerar_mapa_pressao(df_eventos, time_selecionado):
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#f8f9fa', line_color='#333333')
    fig, ax = pitch.draw(figsize=(8, 5))
    
    acoes_def = df_eventos[
        (df_eventos['team'] == time_selecionado) & 
        (df_eventos['type'].isin(['Pressure', 'Duel', 'Tackle', 'Interception']))
    ]
    
    x_coords = [loc[0] for loc in acoes_def['location'].dropna() if isinstance(loc, list)]
    y_coords = [loc[1] for loc in acoes_def['location'].dropna() if isinstance(loc, list)]
    
    pitch.scatter(x_coords, y_coords, s=50, color='#e67e22', alpha=0.6, edgecolors='none', ax=ax)
    ax.set_title(f"Ações Defensivas e Pressão - {time_selecionado}", fontsize=11, color='black')
    return fig

def gerar_grafico_relacao_jogador(df_eventos):
    df_jogadores = df_eventos.dropna(subset=['player'])
    estats = df_jogadores.groupby('player')['type'].value_counts().unstack(fill_value=0)
    
    if 'Pass' not in estats.columns: estats['Pass'] = 0
    if 'Shot' not in estats.columns: estats['Shot'] = 0
    
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(estats['Pass'], estats['Shot'], color='#8e44ad', s=80, alpha=0.7)
    
    for jogador, row in estats.iterrows():
        if row['Pass'] > 20 or row['Shot'] > 1:
            ax.annotate(jogador.split()[-1], (row['Pass'] + 1, row['Shot'] + 0.1), fontsize=8)
            
    ax.set_xlabel("Número de Passes")
    ax.set_ylabel("Número de Finalizações (Chutes)")
    ax.set_title("Relação: Volume de Passes vs Finalizações por Jogador")
    ax.grid(True, linestyle='--', alpha=0.5)
    return fig

# ==========================================
# 4. INTERFACE DO DASHBOARD
# ==========================================
def main():
    st.title("⚽ Dashboard de Análise de Futebol")
    st.write("Selecione os filtros na barra lateral para analisar dados reais de partidas.")

    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("🔍 Filtros da Partida")
    
    with st.spinner("A carregar campeonatos e dados..."):
        df_comp = carregar_competicoes()
        
    comp_selecionada = st.sidebar.selectbox("Escolha o Campeonato:", df_comp['competition_name'].unique())
    df_temp_filtrada = df_comp[df_comp['competition_name'] == comp_selecionada]
    temp_selecionada = st.sidebar.selectbox("Escolha a Temporada:", df_temp_filtrada['season_name'].unique())
    
    linha_selecionada = df_temp_filtrada[df_temp_filtrada['season_name'] == temp_selecionada].iloc[0]
    comp_id, season_id = linha_selecionada['competition_id'], linha_selecionada['season_id']
    
    df_partidas = carregar_partidas(comp_id, season_id)
    df_partidas['jogo_label'] = df_partidas['home_team'] + " vs " + df_partidas['away_team']
    partida_selecionada = st.sidebar.selectbox("Escolha a Partida:", df_partidas['jogo_label'])
    
    info_partida = df_partidas[df_partidas['jogo_label'] == partida_selecionada].iloc[0]
    match_id = info_partida['match_id']

    # --- CARREGAR EVENTOS COM CACHE E SPINNER ---
    with st.spinner("A processar eventos da partida..."):
        df_eventos = carregar_eventos(match_id)

    # --- CABEÇALHO COM MÉTRICAS ---
    st.subheader(f"📌 {comp_selecionada} ({temp_selecionada})")
    total_gols_jogo = int(info_partida['home_score']) + int(info_partida['away_score'])
    
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("Time Mandante", info_partida['home_team'])
    col_p2.metric("Placar Final", f"{info_partida['home_score']} x {info_partida['away_score']}")
    col_p3.metric("Time Visitante", info_partida['away_team'])
    col_p4.metric("Total de Gols do Jogo", f"{total_gols_jogo} Gols", delta="Gols na Partida")

    st.divider()

    # --- ABAS DE NAVEGAÇÃO ---
    tab_estatisticas, tab_mapas, tab_comparador, tab_eventos = st.tabs([
        "📊 Estatísticas Gerais", 
        "🟢 Mapas de Campo & Filtros", 
        "⚔️ Comparador de Jogadores",
        "📋 Tabela de Eventos & Download"
    ])

    # ABA 1: ESTATÍSTICAS
    with tab_estatisticas:
        home_team, away_team = info_partida['home_team'], info_partida['away_team']
        chutes_home = len(df_eventos[(df_eventos['team'] == home_team) & (df_eventos['type'] == 'Shot')])
        chutes_away = len(df_eventos[(df_eventos['team'] == away_team) & (df_eventos['type'] == 'Shot')])
        gols_home, gols_away = int(info_partida['home_score']), int(info_partida['away_score'])
        
        taxa_home = (gols_home / chutes_home * 100) if chutes_home > 0 else 0
        taxa_away = (gols_away / chutes_away * 100) if chutes_away > 0 else 0

        st.markdown("### 🎯 Taxa de Conversão em Gol")
        col_eff1, col_eff2 = st.columns(2)
        col_eff1.metric(f"Conversão - {home_team}", f"{taxa_home:.1f}%", delta=f"{gols_home} gols em {chutes_home} chutes")
        col_eff2.metric(f"Conversão - {away_team}", f"{taxa_away:.1f}%", delta=f"{gols_away} gols em {chutes_away} chutes")

        st.divider()
        fig_rel = gerar_grafico_relacao_jogador(df_eventos)
        st.pyplot(fig_rel)

    # ABA 2: MAPAS DE CAMPO E FORMULÁRIO INTERATIVO
    with tab_mapas:
        st.subheader("Visualização e Filtros Avançados de Eventos")
        
        with st.form("form_filtros_campo"):
            st.markdown("#### ⚙️ Formulário de Personalização do Mapa")
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                time_grafico = st.radio("Selecione a equipe:", [info_partida['home_team'], info_partida['away_team']])
                jogadores_time = df_eventos[df_eventos['team'] == time_grafico]['player'].dropna().unique().tolist()
                jogadores_time.sort()
                jogador_selecionado = st.selectbox("Filtrar por jogador:", ["Todos os Jogadores"] + jogadores_time)
                
            with col_f2:
                minuto_min, minuto_max = st.slider("Intervalo de tempo da partida (Minutos):", 0, 120, (0, 90))
                qtd_max_eventos = st.number_input("Quantidade máxima de eventos a exibir:", min_value=10, max_value=200, value=50, step=10)
                
            with col_f3:
                st.markdown("**Tipos de eventos a exibir:**")
                chk_passes = st.checkbox("Exibir Passes (Setas)", value=True)
                chk_chutes = st.checkbox("Exibir Chutes (Pontos)", value=True)
                
            btn_aplicar = st.form_submit_button("🔄 Aplicar Filtros ao Mapa")
            if btn_aplicar:
                st.session_state['filtros_aplicados'] = True

        col_map1, col_map2 = st.columns(2)
        with col_map1:
            st.markdown("**Mapa de Passes e Chutes Filtrado**")
            fig_passes = gerar_mapa_passes_chutes(
                df_eventos, time_grafico, jogador_selecionado, 
                minuto_min, minuto_max, qtd_max_eventos, chk_passes, chk_chutes
            )
            st.pyplot(fig_passes)

        with col_map2:
            st.markdown("**Mapa de Ações Defensivas (Pressão)**")
            fig_def = gerar_mapa_pressao(df_eventos, time_grafico)
            st.pyplot(fig_def)

    # ABA 3: FORMULÁRIO COMPARADOR DE JOGADORES (COM SESSION STATE)
    with tab_comparador:
        st.subheader("⚔️ Comparador Direto entre Dois Jogadores")
        st.write("Utilize o formulário abaixo para escolher dois atletas e comparar o desempenho na partida:")
        
        lista_todos_jogadores = df_eventos['player'].dropna().unique().tolist()
        lista_todos_jogadores.sort()
        
        with st.form("form_comparacao"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                j1_input = st.selectbox("Selecione o Primeiro Jogador (A):", lista_todos_jogadores, index=0)
            with col_c2:
                j2_input = st.selectbox("Selecione o Segundo Jogador (B):", lista_todos_jogadores, index=min(1, len(lista_todos_jogadores)-1))
                
            btn_comparar = st.form_submit_button("📊 Comparar Jogadores")
            
            # Atualiza o Session State apenas ao submeter o formulário
            if btn_comparar:
                st.session_state['jogador_comparador_a'] = j1_input
                st.session_state['jogador_comparador_b'] = j2_input

        # Utiliza os valores persistidos no Session State
        j1 = st.session_state['jogador_comparador_a'] or j1_input
        j2 = st.session_state['jogador_comparador_b'] or j2_input

        df_j1 = df_eventos[df_eventos['player'] == j1]
        df_j2 = df_eventos[df_eventos['player'] == j2]
        
        p1_total = len(df_j1[df_j1['type'] == 'Pass'])
        p1_certos = len(df_j1[(df_j1['type'] == 'Pass') & (df_j1['pass_outcome'].isna())])
        s1_total = len(df_j1[df_j1['type'] == 'Shot'])
        
        p2_total = len(df_j2[df_j2['type'] == 'Pass'])
        p2_certos = len(df_j2[(df_j2['type'] == 'Pass') & (df_j2['pass_outcome'].isna())])
        s2_total = len(df_j2[df_j2['type'] == 'Shot'])

        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.markdown(f"### 🔵 {j1}")
            st.metric("Total de Passes", p1_total)
            st.metric("Passes Certos", p1_certos)
            st.metric("Finalizações (Chutes)", s1_total)
            
        with col_res2:
            st.markdown(f"### 🔴 {j2}")
            st.metric("Total de Passes", p2_total)
            st.metric("Passes Certos", p2_certos)
            st.metric("Finalizações (Chutes)", s2_total)

    # ABA 4: TABELA DE EVENTOS E DOWNLOAD
    with tab_eventos:
        st.subheader("Eventos Brutos da Partida")
        
        jogador_tabela = st.selectbox("Filtrar tabela por jogador:", ["Todos"] + lista_todos_jogadores)
        df_exibicao = df_eventos.copy()
        if jogador_tabela != "Todos":
            df_exibicao = df_exibicao[df_exibicao['player'] == jogador_tabela]
            
        cols_presentes = [c for c in ['minute', 'second', 'team', 'player', 'type'] if c in df_exibicao.columns]
        df_exibicao = df_exibicao[cols_presentes]
        df_exibicao.columns = ['Minuto', 'Segundo', 'Equipe', 'Jogador', 'Tipo de Evento']
        
        st.dataframe(df_exibicao, use_container_width=True)
        
        csv_data = df_exibicao.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descarregar dados filtrados (CSV)",
            data=csv_data,
            file_name=f"eventos_{partida_selecionada.replace(' ', '_')}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()