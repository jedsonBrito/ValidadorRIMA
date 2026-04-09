import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Aircraft capacity dictionary
AIRCRAFT_CAPACITY = {
    'C208': 9,
    'E295': 136,
    'A319': 144,
    'A320': 180,
    'A321': 224,
    'A20N': 180,
    '32Q': 180,
    'A332': 268,
    '339': 298,
    'AT72': 72,
    'E195': 118,
    'B738': 186,
    'B737': 138,
    'B738W': 186,
    'AT76': 72,
    'A21N': 224
}

PONTE_LABELS = {
    1: 'Ponte de Embarque',
    2: 'Conector Remoto Acessível',
    3: 'Modo Remoto',
    4: 'Sem Passageiros pelo Terminal'
}

PONTE_COLORS = {
    'Ponte de Embarque': '#2E86C1',
    'Conector Remoto Acessível': '#27AE60',
    'Modo Remoto': '#E67E22',
    'Sem Passageiros pelo Terminal': '#95A5A6'
}

def format_date(date_val):
    """Helper function to safely format dates"""
    try:
        if isinstance(date_val, str):
            return pd.to_datetime(date_val).strftime('%d/%m/%Y')
        elif pd.notna(date_val):
            return date_val.strftime('%d/%m/%Y')
        return ''
    except:
        return str(date_val)

def generate_validation_report(df):
    """
    Generate a text report summarizing all validations.
    """
    report = []
    
    # Cabeçalho
    report.append("RELATÓRIO DE VALIDAÇÕES")
    report.append("=" * 50)
    report.append("")

    # 1. Resumo Geral
    report.append("1. RESUMO GERAL")
    report.append("-" * 20)
    total_flights = len(df)
    report.append(f"Total de Operações: {total_flights}")
    report.append(f"Total de Passageiros: {int(df['TOTAL_PAX'].sum()):,}")
    report.append("")

    # 2. Validação de Capacidade
    report.append("2. VALIDAÇÃO DE CAPACIDADE")
    report.append("-" * 20)
    capacity_violations = df[df['EXCEEDS_CAPACITY']].copy()
    report.append(f"Total de violações: {len(capacity_violations)}")
    if not capacity_violations.empty:
        report.append("\nDetalhamento das violações de capacidade:")
        for _, row in capacity_violations.iterrows():
            excesso = row['TOTAL_PAX'] - row['AIRCRAFT_CAPACITY']
            report.append(
                f"Voo: {row['VOO_NUMERO']} - "
                f"Data: {row['CALCO_DATA'].strftime('%d/%m/%Y')} - "
                f"Aeronave: {row['AERONAVE_TIPO']} - "
                f"Capacidade: {row['AIRCRAFT_CAPACITY']} - "
                f"Total PAX: {row['TOTAL_PAX']} - "
                f"Excesso: {excesso}"
            )
    report.append("")

    # 3. Validação Aviação Geral
    report.append("3. VALIDAÇÃO AVIAÇÃO GERAL")
    report.append("-" * 20)
    geral_violations = df[df['GERAL_PAX_VIOLATION']].copy()
    report.append(f"Total de violações: {len(geral_violations)}")
    if not geral_violations.empty:
        report.append("\nDetalhamento das violações de aviação geral:")
        for _, row in geral_violations.iterrows():
            report.append(
                f"Voo: {row['VOO_NUMERO']} - "
                f"Data: {row['CALCO_DATA'].strftime('%d/%m/%Y')} - "
                f"Total PAX: {row['TOTAL_PAX']}"
            )
    report.append("")

    # 4. Validação RPE em Branco
    report.append("4. VALIDAÇÃO RPE EM BRANCO")
    report.append("-" * 20)
    rpe_violations = df[df['RPE_BRANCO_VIOLATION']].copy()
    report.append(f"Total de violações: {len(rpe_violations)}")
    if not rpe_violations.empty:
        report.append("\nDetalhamento das violações de RPE em branco:")
        for _, row in rpe_violations.iterrows():
            report.append(
                f"Voo: {row['VOO_NUMERO']} - "
                f"Data: {row['CALCO_DATA'].strftime('%d/%m/%Y')} - "
                f"Operador: {row['AERONAVE_OPERADOR']}"
            )
    report.append("")

    # 5. Uso de Ponte de Embarque
    report.append("5. USO DE PONTE DE EMBARQUE")
    report.append("-" * 20)
    if 'PONTE_LABEL' in df.columns:
        ponte_summary = df['PONTE_LABEL'].value_counts()
        total = len(df)
        for label, count in ponte_summary.items():
            pct = count / total * 100
            report.append(f"{label}: {count} operações ({pct:.1f}%)")
        invalid_ponte = df['PONTE_CONECTOR_REMOTA'].isna().sum() + \
                        (~df['PONTE_CONECTOR_REMOTA'].isin([1, 2, 3, 4])).sum()
        report.append(f"Valores inválidos/ausentes: {invalid_ponte}")
    report.append("")

    # 6. Estatísticas Finais
    report.append("6. ESTATÍSTICAS FINAIS")
    report.append("-" * 20)
    report.append(f"Percentual de voos com alguma violação: {(len(df[df['EXCEEDS_CAPACITY'] | df['GERAL_PAX_VIOLATION'] | df['RPE_BRANCO_VIOLATION'] | df['HORARIO_INVALIDO']]) / len(df) * 100):.1f}%")
    
    return "\n".join(report)


def validate_passenger_count(df):
    """Validate passenger counts and add necessary columns for analysis."""
    df['AIRCRAFT_CAPACITY'] = df['AERONAVE_TIPO'].map(AIRCRAFT_CAPACITY)
    df['TOTAL_PAX'] = df['PAX_LOCAL'] + df['PAX_CONEXAO_DOMESTICO'] + df['PAX_CONEXAO_INTERNACIONAL']
    df['OCCUPANCY_RATE'] = df.apply(
        lambda row: (row['TOTAL_PAX'] / row['AIRCRAFT_CAPACITY'] * 100) 
        if pd.notnull(row['AIRCRAFT_CAPACITY']) and row['AIRCRAFT_CAPACITY'] > 0 
        else None, 
        axis=1
    )
    df['EXCEEDS_CAPACITY'] = False
    df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'EXCEEDS_CAPACITY'] = \
        df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'TOTAL_PAX'] > df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'AIRCRAFT_CAPACITY']
    df['GERAL_PAX_VIOLATION'] = (df['AERONAVE_OPERADOR'] == 'GERAL') & (df['TOTAL_PAX'] > 0)
    df['RPE_BRANCO_VIOLATION'] = (
        (df['AERONAVE_OPERADOR'] != 'GERAL') & 
        (df['TOTAL_PAX'] == 0) & 
        (~df['SERVICE_TYPE'].isin(['F','M','P','A','X','Y','Z']))
    )
    df['OPERATION_TYPE'] = df['AERONAVE_OPERADOR'].apply(
        lambda x: 'Aviação Geral' if x == 'GERAL' else 'Aviação Comercial'
    )
    return df


def process_flight_data(df):
    """Process flight data and create necessary groupings for visualization."""
    def convert_date(date_str):
        try:
            return pd.to_datetime(date_str, format='%d/%m/%Y')
        except ValueError:
            try:
                return pd.to_datetime(date_str, format='%d/%m/%y')
            except ValueError:
                try:
                    return pd.to_datetime(date_str, dayfirst=True)
                except Exception as e:
                    st.error(f"Erro ao converter a data: {date_str}. Erro: {str(e)}")
                    return None

    df['CALCO_DATA'] = df['CALCO_DATA'].apply(convert_date)
    invalid_dates = df[df['CALCO_DATA'].isna()]
    if not invalid_dates.empty:
        st.warning("Atenção: Foram encontradas datas inválidas nos seguintes registros:")
        st.dataframe(invalid_dates[['CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_MARCAS']])
    df = df.dropna(subset=['CALCO_DATA'])

    operations_by_date = df.groupby(['CALCO_DATA', 'OPERATION_TYPE']).size().reset_index(name='OPERATIONS_COUNT')
    passengers_by_date = df.groupby('CALCO_DATA')['TOTAL_PAX'].sum().reset_index()
    occupancy_by_aircraft = df[df['AIRCRAFT_CAPACITY'].notna()].groupby('AERONAVE_TIPO').agg({
        'OCCUPANCY_RATE': 'mean',
        'TOTAL_PAX': 'sum',
        'AIRCRAFT_CAPACITY': 'first'
    }).reset_index()
    occupancy_by_aircraft = occupancy_by_aircraft.sort_values('OCCUPANCY_RATE', ascending=True)

    return operations_by_date, passengers_by_date, occupancy_by_aircraft


def create_ponte_chart(df, title_suffix=''):
    """
    Cria o gráfico de pizza para uso de ponte de embarque (Campo 18 - PONTE_CONECTOR_REMOTA).
    Regras conforme Portaria nº 2.176/SRA/SIA:
      1 = Ponte de Embarque
      2 = Conector Remoto Acessível
      3 = Modo Remoto
      4 = Sem Passageiros pelo Terminal
    """
    # Converte a coluna para numérico, forçando erros para NaN
    df = df.copy()
    df['PONTE_CONECTOR_REMOTA'] = pd.to_numeric(df['PONTE_CONECTOR_REMOTA'], errors='coerce')

    # Mapeia os valores para os rótulos da portaria
    df['PONTE_LABEL'] = df['PONTE_CONECTOR_REMOTA'].map(PONTE_LABELS)

    # Conta os valores válidos
    ponte_counts = df['PONTE_LABEL'].value_counts().reset_index()
    ponte_counts.columns = ['Modalidade', 'Quantidade']

    # Identifica inválidos/ausentes
    invalid_count = df['PONTE_LABEL'].isna().sum()

    chart_title = 'Uso de Ponte de Embarque (Campo 18 – PONTE_CONECTOR_REMOTO)'
    if title_suffix:
        chart_title += f' – {title_suffix}'

    # Cria o gráfico de pizza
    fig = px.pie(
        ponte_counts,
        values='Quantidade',
        names='Modalidade',
        title=chart_title,
        color='Modalidade',
        color_discrete_map=PONTE_COLORS,
        hole=0.35  # Donut sutil para modernidade
    )

    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Operações: %{value}<br>Percentual: %{percent}<extra></extra>'
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'),
        title_font_color='#2C3E50',
        legend=dict(
            orientation='v',
            yanchor='middle',
            y=0.5,
            xanchor='left',
            x=1.05
        )
    )

    return fig, df, invalid_count, ponte_counts


def create_ponte_by_type_chart(df):
    """
    Cria gráfico de barras agrupadas mostrando o uso de Ponte de Embarque
    separado por Aviação Geral e Aviação Comercial.
    """
    df = df.copy()
    df['PONTE_CONECTOR_REMOTA'] = pd.to_numeric(df['PONTE_CONECTOR_REMOTA'], errors='coerce')
    df['PONTE_LABEL'] = df['PONTE_CONECTOR_REMOTA'].map(PONTE_LABELS)

    # Agrupa por tipo de operação e modalidade
    grouped = (
        df[df['PONTE_LABEL'].notna()]
        .groupby(['OPERATION_TYPE', 'PONTE_LABEL'])
        .size()
        .reset_index(name='Quantidade')
    )
    grouped.columns = ['Tipo de Operação', 'Modalidade', 'Quantidade']

    # Calcula percentual dentro de cada tipo
    totals = grouped.groupby('Tipo de Operação')['Quantidade'].transform('sum')
    grouped['Percentual (%)'] = (grouped['Quantidade'] / totals * 100).round(1)

    fig = px.bar(
        grouped,
        x='Modalidade',
        y='Quantidade',
        color='Tipo de Operação',
        barmode='group',
        title='Uso de Ponte de Embarque por Tipo de Operação',
        template='plotly_white',
        text=grouped['Quantidade'].astype(str) + '<br>(' + grouped['Percentual (%)'].astype(str) + '%)',
        color_discrete_map={
            'Aviação Comercial': '#2E86C1',
            'Aviação Geral': '#E67E22'
        }
    )

    fig.update_traces(textposition='outside')
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'),
        title_font_color='#2C3E50',
        xaxis_title='Modalidade',
        yaxis_title='Número de Operações',
        legend_title='Tipo de Operação',
    )

    return fig


def create_operations_chart(operations_by_date):
    """Create the operations chart with separated operation types."""
    fig = px.bar(
        operations_by_date,
        x='CALCO_DATA',
        y='OPERATIONS_COUNT',
        color='OPERATION_TYPE',
        title='Operações Diárias por Tipo',
        template="plotly_white",
        barmode='stack',
        text='OPERATIONS_COUNT',
        color_discrete_map={
            'Aviação Comercial': '#2E86C1',
            'Aviação Geral': '#E67E22'
        }
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'),
        title_font_color='#2C3E50',
        legend_title_text='Tipo de Operação',
        xaxis_title="Data",
        yaxis_title="Número de Operações"
    )
    fig.update_traces(textposition='inside', texttemplate='%{text:,.0f}')
    return fig


def validate_movement_times(df):
    """Validate movement times based on MOVIMENTO_TIPO."""
    df = df.copy()

    def parse_datetime(date_str, time_str):
        try:
            if pd.isna(date_str) or pd.isna(time_str):
                return None
            if isinstance(date_str, str):
                try:
                    date_obj = pd.to_datetime(date_str, format='%d/%m/%Y')
                except:
                    try:
                        date_obj = pd.to_datetime(date_str)
                    except:
                        return None
            else:
                date_obj = date_str
            try:
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                full_datetime = pd.Timestamp.combine(
                    date_obj.date(),
                    pd.Timestamp.min.time().replace(hour=hour, minute=minute, second=second)
                )
                return full_datetime
            except:
                return None
        except Exception:
            return None

    df['CALCO_DATETIME'] = df.apply(lambda row: parse_datetime(row['CALCO_DATA'], row['CALCO_HORARIO']), axis=1)
    df['TOQUE_DATETIME'] = df.apply(lambda row: parse_datetime(row['TOQUE_DATA'], row['TOQUE_HORARIO']), axis=1)
    df['HORARIO_INVALIDO'] = False
    df['ERRO_VALIDACAO'] = ''

    landing_mask = (df['MOVIMENTO_TIPO'] == 'P') & df['CALCO_DATETIME'].notna() & df['TOQUE_DATETIME'].notna()
    df.loc[landing_mask, 'HORARIO_INVALIDO'] = df.loc[landing_mask, 'CALCO_DATETIME'] < df.loc[landing_mask, 'TOQUE_DATETIME']
    df.loc[landing_mask & df['HORARIO_INVALIDO'], 'ERRO_VALIDACAO'] = 'Calço anterior ao Toque em Pouso'

    takeoff_mask = (df['MOVIMENTO_TIPO'] == 'D') & df['CALCO_DATETIME'].notna() & df['TOQUE_DATETIME'].notna()
    df.loc[takeoff_mask, 'HORARIO_INVALIDO'] = df.loc[takeoff_mask, 'CALCO_DATETIME'] > df.loc[takeoff_mask, 'TOQUE_DATETIME']
    df.loc[takeoff_mask & df['HORARIO_INVALIDO'], 'ERRO_VALIDACAO'] = 'Calço posterior ao Toque em Decolagem'

    missing_times = (
        (df['CALCO_DATETIME'].isna() | df['TOQUE_DATETIME'].isna()) &
        df['MOVIMENTO_TIPO'].isin(['P', 'D'])
    )
    df.loc[missing_times, 'HORARIO_INVALIDO'] = True
    df.loc[missing_times, 'ERRO_VALIDACAO'] = 'Horários incompletos'

    return df


def create_cargo_chart(df):
    """Create the daily cargo chart."""
    cargo_by_date = df.groupby('CALCO_DATA').agg({'CARGA': 'sum', 'CORREIO': 'sum'}).reset_index()
    cargo_melted = pd.melt(cargo_by_date, id_vars=['CALCO_DATA'], value_vars=['CARGA', 'CORREIO'],
                           var_name='Tipo', value_name='Peso')
    fig = px.bar(
        cargo_melted, x='CALCO_DATA', y='Peso', color='Tipo',
        title='Total Diário de Carga e Correio', template="plotly_white",
        barmode='stack', text='Peso',
        color_discrete_map={'CARGA': '#712ECC', 'CORREIO': '#2E89CC'}
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), title_font_color='#2C3E50',
        xaxis_title="Data", yaxis_title="Peso (kg)", legend_title="Tipo"
    )
    fig.update_traces(textposition='inside', texttemplate='%{text:,.0f}')
    return fig


def create_passengers_chart(passengers_by_date):
    """Create the passengers chart."""
    fig = px.bar(
        passengers_by_date, x='CALCO_DATA', y='TOTAL_PAX',
        title='Total Diário de Passageiros', template="plotly_white", text='TOTAL_PAX'
    )
    fig.update_traces(marker_color='#27AE60', textposition='inside', texttemplate='%{text:,.0f}')
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), title_font_color='#2C3E50',
        xaxis_title="Data", yaxis_title="Total de Passageiros"
    )
    return fig


def create_occupancy_chart(occupancy_by_aircraft):
    """Create the occupancy rate chart."""
    fig = px.bar(
        occupancy_by_aircraft, x='AERONAVE_TIPO', y='OCCUPANCY_RATE',
        title='Taxa Média de Ocupação por Tipo de Aeronave', template="plotly_white",
        text=occupancy_by_aircraft['OCCUPANCY_RATE'].round(1).astype(str) + '%'
    )
    fig.update_traces(marker_color='#8E44AD', textposition='outside')
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), title_font_color='#2C3E50',
        xaxis_title="Tipo de Aeronave", yaxis_title="Taxa Média de Ocupação (%)",
        yaxis_range=[0, max(100, occupancy_by_aircraft['OCCUPANCY_RATE'].max() + 5)]
    )
    return fig


def create_geral_validation_chart(df):
    """Create the GERAL validation chart and get invalid flights."""
    geral_flights = df[df['AERONAVE_OPERADOR'] == 'GERAL'].copy()
    geral_flights['VALIDATION_STATUS'] = geral_flights['TOTAL_PAX'].apply(
        lambda x: 'Inválido (PAX > 0)' if x > 0 else 'Válido (PAX = 0)'
    )
    validation_counts = geral_flights['VALIDATION_STATUS'].value_counts().reset_index()
    validation_counts.columns = ['Status', 'Count']
    colors = {'Válido (PAX = 0)': '#27AE60', 'Inválido (PAX > 0)': '#E74C3C'}
    fig = px.pie(
        validation_counts, values='Count', names='Status',
        title='Validação de Passageiros em Voos da Aviação Geral',
        color='Status', color_discrete_map=colors
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), title_font_color='#2C3E50'
    )
    return fig, geral_flights[geral_flights['TOTAL_PAX'] > 0]


def main():
    st.title('Análise de Operações e Passageiros')

    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
        df = validate_passenger_count(df)
        df = validate_movement_times(df)
        operations_by_date, passengers_by_date, occupancy_by_aircraft = process_flight_data(df)
        geral_validation_fig, invalid_geral_flights = create_geral_validation_chart(df)

        # ── Ponte de Embarque – pré-processa PONTE_LABEL no df principal ──────
        _, df_with_ponte, _, _ = create_ponte_chart(df)
        df['PONTE_LABEL'] = df_with_ponte['PONTE_LABEL']

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Operações & Passageiros",
            "Análise de Ocupação",
            "Validação Aviação Geral",
            "Detalhes das Violações",
            "Uso de Ponte de Embarque",
        ])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                total_commercial = len(df[df['OPERATION_TYPE'] == 'Aviação Comercial'])
                st.metric("Total Operações Comerciais", total_commercial)
            with col2:
                total_general = len(df[df['OPERATION_TYPE'] == 'Aviação Geral'])
                st.metric("Total Operações Aviação Geral", total_general)
            st.plotly_chart(create_operations_chart(operations_by_date), use_container_width=True)
            st.plotly_chart(create_passengers_chart(passengers_by_date), use_container_width=True)
            st.plotly_chart(create_cargo_chart(df), use_container_width=True)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Carga (kg)", f"{df['CARGA'].sum():,.0f}")
            with col2:
                st.metric("Total de Correio (kg)", f"{df['CORREIO'].sum():,.0f}")

        with tab2:
            st.plotly_chart(create_occupancy_chart(occupancy_by_aircraft), use_container_width=True)
            avg_occupancy = df[df['OCCUPANCY_RATE'].notna()]['OCCUPANCY_RATE'].mean()
            st.metric("Taxa Média de Ocupação", f"{avg_occupancy:.1f}%")

        with tab3:
            st.plotly_chart(geral_validation_fig, use_container_width=True)
            if not invalid_geral_flights.empty:
                st.subheader('Voos da Aviação Geral Inválidos (PAX > 0)')
                invalid_geral_flights['CALCO_DATA'] = invalid_geral_flights['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    invalid_geral_flights[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_TIPO',
                        'TOTAL_PAX', 'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values('TOTAL_PAX', ascending=False),
                    hide_index=True
                )

        with tab4:
            st.subheader('Detalhes das Violações')

            st.write("### Violações de Capacidade da Aeronave")
            capacity_violations = df[df['EXCEEDS_CAPACITY']].copy()
            if not capacity_violations.empty:
                capacity_violations['CALCO_DATA'] = capacity_violations['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                capacity_violations['EXCESSO_PAX'] = capacity_violations['TOTAL_PAX'] - capacity_violations['AIRCRAFT_CAPACITY']
                st.dataframe(
                    capacity_violations[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_MARCAS', 'AERONAVE_TIPO',
                        'AIRCRAFT_CAPACITY', 'TOTAL_PAX', 'EXCESSO_PAX',
                        'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values(['EXCESSO_PAX', 'CALCO_DATA'], ascending=[False, True]),
                    hide_index=True
                )
            else:
                st.info("Não foram encontradas violações de capacidade.")

            st.write("### Detalhes das Violações de Aviação Geral")
            geral_violations = df[df['GERAL_PAX_VIOLATION']].copy()
            if not geral_violations.empty:
                st.write("#### Todos os Voos com Violações")
                geral_violations['CALCO_DATA'] = geral_violations['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    geral_violations[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_MARCAS', 'AERONAVE_TIPO',
                        'TOTAL_PAX', 'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values(['TOTAL_PAX', 'CALCO_DATA'], ascending=[False, True]),
                    hide_index=True
                )
                st.write("#### Resumo Diário das Violações")
                daily_violations = geral_violations.groupby('CALCO_DATA').agg({
                    'VOO_NUMERO': 'count',
                    'TOTAL_PAX': 'sum',
                    'AERONAVE_MARCAS': lambda x: ', '.join(sorted(set(x)))
                }).reset_index()
                daily_violations.columns = ['Data', 'Número de Voos', 'Total de Passageiros', 'Marcas das Aeronaves']
                st.dataframe(
                    daily_violations.sort_values(['Total de Passageiros', 'Data'], ascending=[False, True]),
                    hide_index=True
                )
            else:
                st.info("Não foram encontradas violações de aviação geral.")

            st.write("### Detalhes de RPE em Branco")
            rpe_branco_violations = df[df['RPE_BRANCO_VIOLATION']].copy()
            if not rpe_branco_violations.empty:
                st.write("#### Voos Comerciais sem Passageiros (Excluindo Carga, Pouso Técnico)")
                rpe_branco_violations['CALCO_DATA'] = rpe_branco_violations['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    rpe_branco_violations[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_MARCAS', 'AERONAVE_TIPO',
                        'SERVICE_TYPE', 'TOTAL_PAX', 'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values('CALCO_DATA', ascending=True),
                    hide_index=True
                )
                st.write("#### Resumo por Operador")
                operator_summary = rpe_branco_violations.groupby(['AERONAVE_OPERADOR', 'SERVICE_TYPE']).agg({
                    'VOO_NUMERO': 'count',
                    'AERONAVE_MARCAS': lambda x: ', '.join(sorted(set(x)))
                }).reset_index()
                operator_summary.columns = ['Operador', 'Tipo de Serviço', 'Número de Voos', 'Marcas das Aeronaves']
                st.dataframe(
                    operator_summary.sort_values(['Operador', 'Número de Voos'], ascending=[True, False]),
                    hide_index=True
                )
                total_commercial = len(df[df['AERONAVE_OPERADOR'] != 'GERAL'])
                violation_percentage = (len(rpe_branco_violations) / total_commercial * 100) if total_commercial > 0 else 0
                st.metric("Percentual de Voos Comerciais com RPE em Branco", f"{violation_percentage:.2f}%",
                          delta_color="inverse")
            else:
                st.info("Não foram encontradas violações de RPE em branco.")

        # ── Aba 5: Uso de Ponte de Embarque ─────────────────────────────────
        with tab5:
            st.subheader('Uso de Ponte de Embarque (Campo 18 – PONTE_CONECTOR_REMOTO)')
            st.caption(
                "Conforme Portaria nº 2.176/SRA/SIA, de 17.07.2019: "
                "**1** = Ponte de Embarque | "
                "**2** = Conector Remoto Acessível | "
                "**3** = Modo Remoto | "
                "**4** = Sem Passageiros pelo Terminal"
            )

            # Filtro por tipo de operação
            filtro_tipo = st.radio(
                "Filtrar por tipo de operação:",
                ["Todas as Operações", "Aviação Comercial", "Aviação Geral"],
                horizontal=True,
                key="ponte_filtro"
            )

            if filtro_tipo == "Aviação Geral":
                df_ponte = df[df['OPERATION_TYPE'] == 'Aviação Geral'].copy()
                title_suffix = 'Aviação Geral'
            elif filtro_tipo == "Aviação Comercial":
                df_ponte = df[df['OPERATION_TYPE'] == 'Aviação Comercial'].copy()
                title_suffix = 'Aviação Comercial'
            else:
                df_ponte = df.copy()
                title_suffix = ''

            # Recalcula gráfico e contagens para o filtro selecionado
            ponte_fig_filtrado, df_ponte_filtrado, invalid_ponte_count_filtrado, ponte_counts_filtrado = \
                create_ponte_chart(df_ponte, title_suffix=title_suffix)

            # Métricas de distribuição
            total_ops = len(df_ponte)
            col1, col2, col3, col4 = st.columns(4)
            for col, (label, color) in zip(
                [col1, col2, col3, col4],
                [
                    ('Ponte de Embarque', '#2E86C1'),
                    ('Conector Remoto Acessível', '#27AE60'),
                    ('Modo Remoto', '#E67E22'),
                    ('Sem Passageiros pelo Terminal', '#95A5A6'),
                ]
            ):
                count = ponte_counts_filtrado.loc[ponte_counts_filtrado['Modalidade'] == label, 'Quantidade'].values
                count_val = int(count[0]) if len(count) > 0 else 0
                pct = count_val / total_ops * 100 if total_ops > 0 else 0
                with col:
                    st.metric(label, f"{count_val}", f"{pct:.1f}% das operações")

            # Gráfico de pizza (filtrado)
            st.plotly_chart(ponte_fig_filtrado, use_container_width=True)

            # Gráfico comparativo Aviação Geral x Aviação Comercial
            st.write("#### Comparativo: Aviação Geral vs. Aviação Comercial")
            st.plotly_chart(create_ponte_by_type_chart(df), use_container_width=True)

            # Tabela detalhada de distribuição
            st.write("#### Distribuição por Modalidade")
            ponte_detail = ponte_counts_filtrado.copy()
            ponte_detail['Percentual (%)'] = (ponte_detail['Quantidade'] / total_ops * 100).round(2)
            ponte_detail = ponte_detail.sort_values('Quantidade', ascending=False).reset_index(drop=True)
            st.dataframe(ponte_detail, hide_index=True, use_container_width=True)

            # Alerta de valores inválidos
            if invalid_ponte_count_filtrado > 0:
                st.warning(
                    f"⚠️ Foram encontrados **{invalid_ponte_count_filtrado}** registros com valor inválido ou ausente "
                    f"no campo PONTE_CONECTOR_REMOTA (esperado: 1, 2, 3 ou 4)."
                )
                invalid_rows = df_ponte_filtrado[df_ponte_filtrado['PONTE_LABEL'].isna()].copy()
                if 'CALCO_DATA' in invalid_rows.columns:
                    invalid_rows['CALCO_DATA'] = invalid_rows['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.write("#### Registros com Valor Inválido/Ausente")
                cols_to_show = ['CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR',
                                'AERONAVE_TIPO', 'PONTE_CONECTOR_REMOTA']
                cols_available = [c for c in cols_to_show if c in invalid_rows.columns]
                st.dataframe(invalid_rows[cols_available].sort_values('CALCO_DATA'), hide_index=True)
            else:
                st.success("✅ Todos os registros possuem valor válido no campo PONTE_CONECTOR_REMOTA.")

        # ── Estatísticas Gerais ──────────────────────────────────────────────
        st.subheader('Estatísticas Gerais')
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total de Operações", len(df))
        with col2:
            st.metric("Total de Passageiros", int(df['TOTAL_PAX'].sum()))
        with col3:
            st.metric("Violações de Capacidade", int(df['EXCEEDS_CAPACITY'].sum()), delta_color="inverse")
        with col4:
            st.metric("Violações PAX Aviação Geral", int(df['GERAL_PAX_VIOLATION'].sum()), delta_color="inverse")
        with col5:
            st.metric("RPE em Branco", int(df['RPE_BRANCO_VIOLATION'].sum()), delta_color="inverse")

        report_text = generate_validation_report(df)
        st.download_button(
            label="Baixar Relatório de Validações",
            data=report_text,
            file_name="relatorio_validacoes.txt",
            mime="text/plain",
        )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Análise de Voos",
        page_icon="✈️",
        layout="wide"
    )
    st.markdown("""
        <style>
        .stApp { background-color: #F5F7FA; }
        .st-emotion-cache-10trblm { color: #2C3E50; }
        .st-emotion-cache-1629p8f { color: #2C3E50; }
        .st-emotion-cache-1inwz65 { color: #2C3E50; }
        div[data-testid="stMetricValue"] { color: #2C3E50; }
        </style>
    """, unsafe_allow_html=True)
    main()