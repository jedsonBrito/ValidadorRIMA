import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

AIRCRAFT_CAPACITY = {
    'C208': 9, 'E295': 136, 'A319': 144, 'A320': 180, 'A321': 224,
    'A20N': 180, '32Q': 180, 'A332': 268, '339': 298, 'AT72': 72,
    'E195': 118, 'B738': 186, 'B737': 138, 'B738W': 186, 'AT76': 72,
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

# Campos obrigatórios conforme portaria (campo → descrição amigável)
CAMPOS_OBRIGATORIOS = {
    'COD_RIMA': 'Cód. RIMA (Campo 1)',
    'MOVIMENTO_TIPO': 'Tipo de Movimento (Campo 2)',
    'AERONAVE_MARCAS': 'Marcas da Aeronave (Campo 3)',
    'AERONAVE_TIPO': 'Tipo de Aeronave (Campo 4)',
    'AERONAVE_OPERADOR': 'Operador (Campo 5)',
    'VOO_OUTRO_AEROPORTO': 'Aeroporto Anterior/Posterior (Campo 6)',
    'VOO_NUMERO': 'Número do Voo (Campo 7)',
    'SERVICE_TYPE': 'Tipo de Serviço (Campo 8)',
    'NATUREZA': 'Natureza (Campo 9)',
    'PREVISTO_DATA': 'Data Prevista (Campo 10)',
    'PREVISTO_HORARIO': 'Horário Previsto (Campo 11)',
    'CALCO_DATA': 'Data Calço (Campo 12)',
    'CALCO_HORARIO': 'Horário Calço (Campo 13)',
    'TOQUE_DATA': 'Data Toque (Campo 14)',
    'TOQUE_HORARIO': 'Horário Toque (Campo 15)',
    'CABECEIRA': 'Cabeceira (Campo 16)',
    'BOX': 'Box/Posição Pátio (Campo 17)',
    'PONTE_CONECTOR_REMOTA': 'Ponte/Conector (Campo 18)',
    'TERMINAL': 'Terminal (Campo 19)',
    'PAX_LOCAL': 'PAX Local (Campo 20)',
    'PAX_CONEXAO_DOMESTICO': 'PAX Conexão Doméstico (Campo 21)',
    'PAX_CONEXAO_INTERNACIONAL': 'PAX Conexão Internacional (Campo 22)',
    'CORREIO': 'Correio kg (Campo 23)',
    'CARGA': 'Carga kg (Campo 24)',
}

# Campos opcionais (25 e 26) — validados se presentes, mas não exigidos
CAMPOS_OPCIONAIS = {
    'RETORNO_ALTERNADO': 'Retorno/Alternado (Campo 25)',
    'CONTESTACAO': 'Contestação (Campo 26)',
}

# Valores válidos por campo (enumerados)
VALORES_VALIDOS = {
    'MOVIMENTO_TIPO': ['P', 'D'],
    'NATUREZA': ['D', 'I'],
    'PONTE_CONECTOR_REMOTA': [1, 2, 3, 4],
    'RETORNO_ALTERNADO': ['R', 'A', 'N', '', None],
    'CONTESTACAO': ['NE', 'NC', 'CO', 'DV', '', None],
    'SERVICE_TYPE': [
        'J', 'C', 'F', 'H', 'W', 'G', 'P', 'Q', 'T', 'M', 'X',
        'I', 'E', 'A', 'N', 'B', 'D', 'K', 'L', 'O', 'R', 'S',
        'U', 'V', 'Y', 'Z'
    ],
}

# Regex de formato
RE_DATA = re.compile(r'^\d{2}/\d{2}/\d{4}$')
RE_HORARIO = re.compile(r'^\d{2}:\d{2}$')
RE_OACI_ICAO = re.compile(r'^[A-Z0-9]{4}$')      # aeroporto: 4 caracteres alfanuméricos
RE_OACI_OPERADOR = re.compile(r'^[A-Z0-9]{2,3}$')  # designador de operador


# ─────────────────────────────────────────────────────────────
# VALIDAÇÃO DE CAMPOS — NOVA FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────────────────────────

def validate_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Executa todas as validações de campos (obrigatórios, formatos e regras
    de negócio dos metadados do RIMA). Retorna um DataFrame de erros com
    colunas: LINHA, CAMPO, DESCRICAO_CAMPO, VALOR_ENCONTRADO, TIPO_ERRO, DETALHE.
    """
    errors = []

    def add_error(idx, campo, descricao, valor, tipo, detalhe):
        errors.append({
            'LINHA': idx + 2,          # +2: 1-indexed + cabeçalho
            'CAMPO': campo,
            'DESCRICAO_CAMPO': descricao,
            'VALOR_ENCONTRADO': str(valor) if pd.notna(valor) else '(vazio)',
            'TIPO_ERRO': tipo,
            'DETALHE': detalhe,
        })

    def is_blank(val):
        if val is None:
            return True
        if isinstance(val, float) and pd.isna(val):
            return True
        if isinstance(val, str) and val.strip() == '':
            return True
        return False

    def valid_date(val):
        if is_blank(val):
            return False
        s = str(val).strip()
        if not RE_DATA.match(s):
            return False
        try:
            datetime.strptime(s, '%d/%m/%Y')
            return True
        except ValueError:
            return False

    def valid_time(val):
        if is_blank(val):
            return False
        s = str(val).strip()
        if not RE_HORARIO.match(s):
            return False
        h, m = s.split(':')
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59

    for idx, row in df.iterrows():

        # ── 1. Campos obrigatórios: nulos/vazios ────────────────────────────
        for campo, desc in CAMPOS_OBRIGATORIOS.items():
            if campo not in df.columns:
                continue
            val = row.get(campo)
            if is_blank(val):
                add_error(idx, campo, desc, val, 'CAMPO VAZIO', f'{desc} é obrigatório e está vazio/nulo.')

        # ── 2. Campo 2 – MOVIMENTO_TIPO: apenas 'P' ou 'D' ──────────────────
        val = row.get('MOVIMENTO_TIPO')
        if not is_blank(val) and str(val).strip() not in VALORES_VALIDOS['MOVIMENTO_TIPO']:
            add_error(idx, 'MOVIMENTO_TIPO', CAMPOS_OBRIGATORIOS.get('MOVIMENTO_TIPO', 'Tipo Movimento'),
                      val, 'VALOR INVÁLIDO', f"Esperado 'P' ou 'D'. Encontrado: '{val}'.")

        # ── 3. Campo 6 – VOO_OUTRO_AEROPORTO: formato OACI (4 letras maiúsculas)
        val = row.get('VOO_OUTRO_AEROPORTO')
        if not is_blank(val):
            s = str(val).strip()
            if s not in ('0', 'ZZZZ') and not RE_OACI_ICAO.match(s):
                add_error(idx, 'VOO_OUTRO_AEROPORTO',
                          CAMPOS_OBRIGATORIOS.get('VOO_OUTRO_AEROPORTO', 'Aeroporto Ant/Post'),
                          val, 'FORMATO INVÁLIDO',
                          f"Código de aeroporto deve ter 4 caracteres alfanuméricos. Encontrado: '{val}'.")

        # ── 4. Campo 7 – VOO_NUMERO: numérico ───────────────────────────────
        val = row.get('VOO_NUMERO')
        if not is_blank(val):
            try:
                int(float(str(val).strip()))
            except ValueError:
                add_error(idx, 'VOO_NUMERO', CAMPOS_OBRIGATORIOS.get('VOO_NUMERO', 'Nº Voo'),
                          val, 'FORMATO INVÁLIDO', f"Deve ser numérico. Encontrado: '{val}'.")

        # ── 5. Campo 8 – SERVICE_TYPE: valores IATA + Y/Z ───────────────────
        val = row.get('SERVICE_TYPE')
        if not is_blank(val):
            s = str(val).strip().upper()
            if s not in [v.upper() for v in VALORES_VALIDOS['SERVICE_TYPE']]:
                add_error(idx, 'SERVICE_TYPE', CAMPOS_OBRIGATORIOS.get('SERVICE_TYPE', 'Tipo Serviço'),
                          val, 'VALOR INVÁLIDO',
                          f"SERVICE_TYPE '{val}' não consta no SSIM IATA nem nos códigos padrão Y/Z.")

        # ── 6. Campo 9 – NATUREZA: 'D' ou 'I' ───────────────────────────────
        val = row.get('NATUREZA')
        if not is_blank(val) and str(val).strip() not in VALORES_VALIDOS['NATUREZA']:
            add_error(idx, 'NATUREZA', CAMPOS_OBRIGATORIOS.get('NATUREZA', 'Natureza'),
                      val, 'VALOR INVÁLIDO', f"Esperado 'D' (doméstico) ou 'I' (internacional). Encontrado: '{val}'.")

        # ── 7. Campos de DATA: formato DD/MM/AAAA ────────────────────────────
        for campo in ['PREVISTO_DATA', 'CALCO_DATA', 'TOQUE_DATA']:
            desc = CAMPOS_OBRIGATORIOS.get(campo, campo)
            val = row.get(campo)
            if not is_blank(val):
                s = str(val).strip()
                # Se já foi convertido para Timestamp pelo pandas, formata e verifica
                if hasattr(val, 'strftime'):
                    pass  # datetime válido
                elif not valid_date(s):
                    add_error(idx, campo, desc, val, 'FORMATO INVÁLIDO',
                              f"Data deve ser DD/MM/AAAA. Encontrado: '{val}'.")

        # ── 8. Campos de HORÁRIO: formato HH:MM ──────────────────────────────
        for campo in ['PREVISTO_HORARIO', 'CALCO_HORARIO', 'TOQUE_HORARIO']:
            desc = CAMPOS_OBRIGATORIOS.get(campo, campo)
            val = row.get(campo)
            if not is_blank(val):
                s = str(val).strip()
                if not valid_time(s):
                    add_error(idx, campo, desc, val, 'FORMATO INVÁLIDO',
                              f"Horário deve ser HH:MM (00-23:00-59). Encontrado: '{val}'.")

        # ── 9. Campo 17 – BOX: N/A ou valor cadastrado (não vazio) ──────────
        val = row.get('BOX')
        if is_blank(val):
            add_error(idx, 'BOX', CAMPOS_OBRIGATORIOS.get('BOX', 'Box Pátio'),
                      val, 'CAMPO VAZIO',
                      "Campo BOX deve ser preenchido com o identificador da posição ou 'N/A'.")

        # ── 10. Campo 18 – PONTE_CONECTOR_REMOTA: 1, 2, 3 ou 4 ──────────────
        val = row.get('PONTE_CONECTOR_REMOTA')
        if not is_blank(val):
            try:
                v = int(float(str(val).strip()))
                if v not in VALORES_VALIDOS['PONTE_CONECTOR_REMOTA']:
                    add_error(idx, 'PONTE_CONECTOR_REMOTA',
                              CAMPOS_OBRIGATORIOS.get('PONTE_CONECTOR_REMOTA', 'Ponte/Conector'),
                              val, 'VALOR INVÁLIDO', f"Esperado 1, 2, 3 ou 4. Encontrado: '{val}'.")
            except ValueError:
                add_error(idx, 'PONTE_CONECTOR_REMOTA',
                          CAMPOS_OBRIGATORIOS.get('PONTE_CONECTOR_REMOTA', 'Ponte/Conector'),
                          val, 'FORMATO INVÁLIDO', f"Deve ser numérico (1-4). Encontrado: '{val}'.")

        # ── 11. Campo 19 – TERMINAL: N/A ou valor preenchido ─────────────────
        val = row.get('TERMINAL')
        if is_blank(val):
            add_error(idx, 'TERMINAL', CAMPOS_OBRIGATORIOS.get('TERMINAL', 'Terminal'),
                      val, 'CAMPO VAZIO',
                      "Campo TERMINAL deve ser preenchido com o identificador ou 'N/A'.")

        # ── 12. Campos numéricos PAX/CARGA/CORREIO: >= 0 ─────────────────────
        for campo in ['PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL',
                      'CORREIO', 'CARGA']:
            desc = CAMPOS_OBRIGATORIOS.get(campo, campo)
            val = row.get(campo)
            if not is_blank(val):
                try:
                    n = float(str(val).strip())
                    if n < 0:
                        add_error(idx, campo, desc, val, 'VALOR INVÁLIDO',
                                  f"Valores negativos não são permitidos. Encontrado: {val}.")
                except ValueError:
                    add_error(idx, campo, desc, val, 'FORMATO INVÁLIDO',
                              f"Deve ser numérico (≥ 0). Encontrado: '{val}'.")

        # ── 13. Campo 25 – RETORNO_ALTERNADO: R, A, N ou vazio (opcional) ────
        val = row.get('RETORNO_ALTERNADO')
        if not is_blank(val) and str(val).strip() not in ['R', 'A', 'N', '']:
            add_error(idx, 'RETORNO_ALTERNADO',
                      CAMPOS_OPCIONAIS.get('RETORNO_ALTERNADO', 'Retorno/Alternado'),
                      val, 'VALOR INVÁLIDO',
                      f"Esperado 'R', 'A', 'N' ou vazio. Encontrado: '{val}'.")

        # ── 14. Campo 26 – CONTESTACAO: NE, NC, CO, DV ou vazio (opcional) ───
        val = row.get('CONTESTACAO')
        if not is_blank(val) and str(val).strip() not in ['NE', 'NC', 'CO', 'DV', '']:
            add_error(idx, 'CONTESTACAO',
                      CAMPOS_OPCIONAIS.get('CONTESTACAO', 'Contestação'),
                      val, 'VALOR INVÁLIDO',
                      f"Esperado 'NE', 'NC', 'CO', 'DV' ou vazio. Encontrado: '{val}'.")

        # ── 15. Consistência NATUREZA x AERONAVE_MARCAS ──────────────────────
        # Matrícula brasileira começa com PS-, PP-, PR-, PT-, PU-.
        # Aeronaves da Força Aérea Brasileira (prefixo FAB) também são domésticas.
        marcas = str(row.get('AERONAVE_MARCAS', '') or '').strip().upper()
        natureza = str(row.get('NATUREZA', '') or '').strip().upper()
        br_prefix = marcas[:2] in ('PS', 'PP', 'PR', 'PT', 'PU') or marcas.startswith('FAB')
        if natureza == 'D' and marcas and not br_prefix:
            add_error(idx, 'NATUREZA', CAMPOS_OBRIGATORIOS.get('NATUREZA', 'Natureza'),
                      natureza, 'INCONSISTÊNCIA',
                      f"NATUREZA='D' (doméstico) mas matrícula '{marcas}' parece estrangeira.")
        if natureza == 'I' and marcas and br_prefix:
            # NATUREZA='I' com matrícula BR é possível (fretamento p/ exterior),
            # então apenas aviso, não erro.
            add_error(idx, 'NATUREZA', CAMPOS_OBRIGATORIOS.get('NATUREZA', 'Natureza'),
                      natureza, 'AVISO',
                      f"NATUREZA='I' com matrícula brasileira '{marcas}' — verificar se é fretamento internacional.")

    errors_df = pd.DataFrame(errors, columns=[
        'LINHA', 'CAMPO', 'DESCRICAO_CAMPO', 'VALOR_ENCONTRADO', 'TIPO_ERRO', 'DETALHE'
    ])
    return errors_df


def render_tab_campos(df: pd.DataFrame):
    """Renderiza a aba de Validação de Campos no Streamlit."""
    st.subheader('Validação de Campos — Obrigatórios, Formatos e Regras de Negócio')
    st.caption(
        "Baseado na Portaria nº 2.176/SRA/SIA e nos metadados do RIMA (Campos 1–26). "
        "Campos opcionais (25 e 26) são validados quando preenchidos."
    )

    with st.spinner('Executando validações de campos...'):
        erros_df = validate_fields(df)

    total_erros = len(erros_df)
    total_linhas = len(df)

    if total_erros == 0:
        st.success(f'✅ Nenhum erro de campo encontrado nas {total_linhas} operações.')
        return

    # ── KPIs ──────────────────────────────────────────────────────────────
    linhas_com_erro = erros_df['LINHA'].nunique()
    campos_afetados = erros_df['CAMPO'].nunique()

    tipo_counts = erros_df['TIPO_ERRO'].value_counts()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Total de Erros', total_erros)
    col2.metric('Linhas com Erro', f'{linhas_com_erro} / {total_linhas}',
                f'{linhas_com_erro / total_linhas * 100:.1f}%')
    col3.metric('Campos Afetados', campos_afetados)
    col4.metric('Campos Vazios', int(tipo_counts.get('CAMPO VAZIO', 0)), delta_color='inverse')
    col5.metric('Formato/Valor Inválido',
                int(tipo_counts.get('FORMATO INVÁLIDO', 0) + tipo_counts.get('VALOR INVÁLIDO', 0)),
                delta_color='inverse')

    st.markdown('---')

    # ── Gráfico: erros por campo ───────────────────────────────────────────
    erros_por_campo = (
        erros_df.groupby(['CAMPO', 'TIPO_ERRO'])
        .size()
        .reset_index(name='Quantidade')
    )
    fig_campos = px.bar(
        erros_por_campo,
        x='CAMPO', y='Quantidade', color='TIPO_ERRO',
        title='Erros por Campo e Tipo',
        template='plotly_white',
        barmode='stack',
        color_discrete_map={
            'CAMPO VAZIO': '#E74C3C',
            'FORMATO INVÁLIDO': '#E67E22',
            'VALOR INVÁLIDO': '#F39C12',
            'INCONSISTÊNCIA': '#8E44AD',
            'AVISO': '#3498DB',
        }
    )
    fig_campos.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), xaxis_tickangle=-35,
        xaxis_title='Campo', yaxis_title='Quantidade de Erros',
        legend_title='Tipo de Erro'
    )

    # ── Gráfico: distribuição por tipo de erro ─────────────────────────────
    tc = tipo_counts.reset_index()
    tc.columns = ['Tipo', 'Quantidade']
    fig_tipo = px.pie(
        tc, names='Tipo', values='Quantidade',
        title='Distribuição por Tipo de Erro',
        color='Tipo',
        color_discrete_map={
            'CAMPO VAZIO': '#E74C3C',
            'FORMATO INVÁLIDO': '#E67E22',
            'VALOR INVÁLIDO': '#F39C12',
            'INCONSISTÊNCIA': '#8E44AD',
            'AVISO': '#3498DB',
        },
        hole=0.4
    )
    fig_tipo.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50')
    )

    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        st.plotly_chart(fig_campos, use_container_width=True)
    with col_g2:
        st.plotly_chart(fig_tipo, use_container_width=True)

    st.markdown('---')

    # ── Filtros interativos ────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        tipos_disponiveis = sorted(erros_df['TIPO_ERRO'].unique().tolist())
        tipo_selecionado = st.multiselect(
            'Filtrar por Tipo de Erro:', tipos_disponiveis,
            default=tipos_disponiveis, key='campo_tipo_filter'
        )
    with col_f2:
        campos_disponiveis = sorted(erros_df['CAMPO'].unique().tolist())
        campo_selecionado = st.multiselect(
            'Filtrar por Campo:', campos_disponiveis,
            default=campos_disponiveis, key='campo_campo_filter'
        )

    erros_filtrado = erros_df[
        erros_df['TIPO_ERRO'].isin(tipo_selecionado) &
        erros_df['CAMPO'].isin(campo_selecionado)
    ].sort_values(['TIPO_ERRO', 'CAMPO', 'LINHA'])

    st.write(f'#### Registros de Erro ({len(erros_filtrado)} ocorrências)')
    st.dataframe(erros_filtrado, hide_index=True, use_container_width=True)

    # ── Resumo por campo ───────────────────────────────────────────────────
    st.write('#### Resumo por Campo')
    resumo = (
        erros_df.groupby(['CAMPO', 'DESCRICAO_CAMPO', 'TIPO_ERRO'])
        .size()
        .reset_index(name='Ocorrências')
        .sort_values(['TIPO_ERRO', 'Ocorrências'], ascending=[True, False])
    )
    st.dataframe(resumo, hide_index=True, use_container_width=True)

    # ── Download ───────────────────────────────────────────────────────────
    csv_erros = erros_df.to_csv(index=False, sep=';').encode('utf-8-sig')
    st.download_button(
        '⬇️ Baixar Erros de Campos (CSV)',
        data=csv_erros,
        file_name='erros_campos_rima.csv',
        mime='text/csv'
    )


# ─────────────────────────────────────────────────────────────
# FUNÇÕES ORIGINAIS (mantidas integralmente)
# ─────────────────────────────────────────────────────────────

def format_date(date_val):
    try:
        if isinstance(date_val, str):
            return pd.to_datetime(date_val).strftime('%d/%m/%Y')
        elif pd.notna(date_val):
            return date_val.strftime('%d/%m/%Y')
        return ''
    except:
        return str(date_val)


def generate_validation_report(df):
    report = []
    report.append("RELATÓRIO DE VALIDAÇÕES")
    report.append("=" * 50)
    report.append("")
    report.append("1. RESUMO GERAL")
    report.append("-" * 20)
    total_flights = len(df)
    report.append(f"Total de Operações: {total_flights}")
    report.append(f"Total de Passageiros: {int(df['TOTAL_PAX'].sum()):,}")
    report.append("")
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
    report.append("6. ESTATÍSTICAS FINAIS")
    report.append("-" * 20)
    report.append(
        f"Percentual de voos com alguma violação: "
        f"{(len(df[df['EXCEEDS_CAPACITY'] | df['GERAL_PAX_VIOLATION'] | df['RPE_BRANCO_VIOLATION'] | df['HORARIO_INVALIDO']]) / len(df) * 100):.1f}%"
    )
    return "\n".join(report)


def validate_passenger_count(df):
    df['AIRCRAFT_CAPACITY'] = df['AERONAVE_TIPO'].map(AIRCRAFT_CAPACITY)
    df['TOTAL_PAX'] = df['PAX_LOCAL'] + df['PAX_CONEXAO_DOMESTICO'] + df['PAX_CONEXAO_INTERNACIONAL']
    df['OCCUPANCY_RATE'] = df.apply(
        lambda row: (row['TOTAL_PAX'] / row['AIRCRAFT_CAPACITY'] * 100)
        if pd.notnull(row['AIRCRAFT_CAPACITY']) and row['AIRCRAFT_CAPACITY'] > 0
        else None, axis=1
    )
    df['EXCEEDS_CAPACITY'] = False
    df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'EXCEEDS_CAPACITY'] = \
        df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'TOTAL_PAX'] > df.loc[df['AIRCRAFT_CAPACITY'].notna(), 'AIRCRAFT_CAPACITY']
    df['GERAL_PAX_VIOLATION'] = (df['AERONAVE_OPERADOR'] == 'GERAL') & (df['TOTAL_PAX'] > 0)
    df['RPE_BRANCO_VIOLATION'] = (
        (df['AERONAVE_OPERADOR'] != 'GERAL') &
        (df['TOTAL_PAX'] == 0) &
        (~df['SERVICE_TYPE'].isin(['F', 'M', 'P', 'A', 'X', 'Y', 'Z']))
    )
    df['OPERATION_TYPE'] = df['AERONAVE_OPERADOR'].apply(
        lambda x: 'Aviação Geral' if x == 'GERAL' else 'Aviação Comercial'
    )
    return df


def process_flight_data(df):
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
        'OCCUPANCY_RATE': 'mean', 'TOTAL_PAX': 'sum', 'AIRCRAFT_CAPACITY': 'first'
    }).reset_index()
    occupancy_by_aircraft = occupancy_by_aircraft.sort_values('OCCUPANCY_RATE', ascending=True)
    return operations_by_date, passengers_by_date, occupancy_by_aircraft


def create_ponte_chart(df, title_suffix=''):
    df = df.copy()
    df['PONTE_CONECTOR_REMOTA'] = pd.to_numeric(df['PONTE_CONECTOR_REMOTA'], errors='coerce')
    df['PONTE_LABEL'] = df['PONTE_CONECTOR_REMOTA'].map(PONTE_LABELS)
    ponte_counts = df['PONTE_LABEL'].value_counts().reset_index()
    ponte_counts.columns = ['Modalidade', 'Quantidade']
    invalid_count = df['PONTE_LABEL'].isna().sum()
    chart_title = 'Uso de Ponte de Embarque (Campo 18 – PONTE_CONECTOR_REMOTO)'
    if title_suffix:
        chart_title += f' – {title_suffix}'
    fig = px.pie(ponte_counts, values='Quantidade', names='Modalidade', title=chart_title,
                 color='Modalidade', color_discrete_map=PONTE_COLORS, hole=0.35)
    fig.update_traces(textposition='inside', textinfo='percent+label',
                      hovertemplate='<b>%{label}</b><br>Operações: %{value}<br>Percentual: %{percent}<extra></extra>')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      legend=dict(orientation='v', yanchor='middle', y=0.5, xanchor='left', x=1.05))
    return fig, df, invalid_count, ponte_counts


def create_ponte_by_type_chart(df):
    df = df.copy()
    df['PONTE_CONECTOR_REMOTA'] = pd.to_numeric(df['PONTE_CONECTOR_REMOTA'], errors='coerce')
    df['PONTE_LABEL'] = df['PONTE_CONECTOR_REMOTA'].map(PONTE_LABELS)
    grouped = (df[df['PONTE_LABEL'].notna()].groupby(['OPERATION_TYPE', 'PONTE_LABEL'])
               .size().reset_index(name='Quantidade'))
    grouped.columns = ['Tipo de Operação', 'Modalidade', 'Quantidade']
    totals = grouped.groupby('Tipo de Operação')['Quantidade'].transform('sum')
    grouped['Percentual (%)'] = (grouped['Quantidade'] / totals * 100).round(1)
    fig = px.bar(grouped, x='Modalidade', y='Quantidade', color='Tipo de Operação', barmode='group',
                 title='Uso de Ponte de Embarque por Tipo de Operação', template='plotly_white',
                 text=grouped['Quantidade'].astype(str) + '<br>(' + grouped['Percentual (%)'].astype(str) + '%)',
                 color_discrete_map={'Aviação Comercial': '#2E86C1', 'Aviação Geral': '#E67E22'})
    fig.update_traces(textposition='outside')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      xaxis_title='Modalidade', yaxis_title='Número de Operações', legend_title='Tipo de Operação')
    return fig


def create_operations_chart(operations_by_date):
    fig = px.bar(operations_by_date, x='CALCO_DATA', y='OPERATIONS_COUNT', color='OPERATION_TYPE',
                 title='Operações Diárias por Tipo', template="plotly_white", barmode='stack',
                 text='OPERATIONS_COUNT',
                 color_discrete_map={'Aviação Comercial': '#2E86C1', 'Aviação Geral': '#E67E22'})
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      legend_title_text='Tipo de Operação', xaxis_title="Data", yaxis_title="Número de Operações")
    fig.update_traces(textposition='inside', texttemplate='%{text:,.0f}')
    return fig


def validate_movement_times(df):
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
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            return pd.Timestamp.combine(
                date_obj.date(),
                pd.Timestamp.min.time().replace(hour=hour, minute=minute, second=second)
            )
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
    cargo_by_date = df.groupby('CALCO_DATA').agg({'CARGA': 'sum', 'CORREIO': 'sum'}).reset_index()
    cargo_melted = pd.melt(cargo_by_date, id_vars=['CALCO_DATA'], value_vars=['CARGA', 'CORREIO'],
                           var_name='Tipo', value_name='Peso')
    fig = px.bar(cargo_melted, x='CALCO_DATA', y='Peso', color='Tipo',
                 title='Total Diário de Carga e Correio', template="plotly_white",
                 barmode='stack', text='Peso',
                 color_discrete_map={'CARGA': '#712ECC', 'CORREIO': '#2E89CC'})
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      xaxis_title="Data", yaxis_title="Peso (kg)", legend_title="Tipo")
    fig.update_traces(textposition='inside', texttemplate='%{text:,.0f}')
    return fig


def create_passengers_chart(passengers_by_date):
    fig = px.bar(passengers_by_date, x='CALCO_DATA', y='TOTAL_PAX',
                 title='Total Diário de Passageiros', template="plotly_white", text='TOTAL_PAX')
    fig.update_traces(marker_color='#27AE60', textposition='inside', texttemplate='%{text:,.0f}')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      xaxis_title="Data", yaxis_title="Total de Passageiros")
    return fig


def create_occupancy_chart(occupancy_by_aircraft):
    fig = px.bar(occupancy_by_aircraft, x='AERONAVE_TIPO', y='OCCUPANCY_RATE',
                 title='Taxa Média de Ocupação por Tipo de Aeronave', template="plotly_white",
                 text=occupancy_by_aircraft['OCCUPANCY_RATE'].round(1).astype(str) + '%')
    fig.update_traces(marker_color='#8E44AD', textposition='outside')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50',
                      xaxis_title="Tipo de Aeronave", yaxis_title="Taxa Média de Ocupação (%)",
                      yaxis_range=[0, max(100, occupancy_by_aircraft['OCCUPANCY_RATE'].max() + 5)])
    return fig


def create_geral_validation_chart(df):
    geral_flights = df[df['AERONAVE_OPERADOR'] == 'GERAL'].copy()
    geral_flights['VALIDATION_STATUS'] = geral_flights['TOTAL_PAX'].apply(
        lambda x: 'Inválido (PAX > 0)' if x > 0 else 'Válido (PAX = 0)'
    )
    validation_counts = geral_flights['VALIDATION_STATUS'].value_counts().reset_index()
    validation_counts.columns = ['Status', 'Count']
    colors = {'Válido (PAX = 0)': '#27AE60', 'Inválido (PAX > 0)': '#E74C3C'}
    fig = px.pie(validation_counts, values='Count', names='Status',
                 title='Validação de Passageiros em Voos da Aviação Geral',
                 color='Status', color_discrete_map=colors)
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='#2C3E50'), title_font_color='#2C3E50')
    return fig, geral_flights[geral_flights['TOTAL_PAX'] > 0]


# ─────────────────────────────────────────────────────────────
# LEITURA PADRONIZADA DO RIMA
# ─────────────────────────────────────────────────────────────

def read_rima_csv(file):
    """
    Lê um CSV de RIMA preservando textos como 'N/A', 'NA', 'NULL' (que o
    pandas, por padrão, converteria em NaN). Apenas células realmente vazias
    tornam-se NaN.
    """
    return pd.read_csv(
        file, sep=';', encoding='utf-8',
        keep_default_na=False, na_values=['']
    )


# ─────────────────────────────────────────────────────────────
# FECHAMENTO / CONCILIAÇÃO ENTRE DOIS RIMAS
# ─────────────────────────────────────────────────────────────

def compute_fechamento_summary(df: pd.DataFrame) -> dict:
    """
    Calcula os totais consolidados de um RIMA para fins de fechamento:
    ATM (movimentos), passageiros, conexões, carga e correio.
    """
    d = df.copy()

    # Garante numéricos (campos podem vir como string dependendo da origem)
    for c in ['PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL',
              'CORREIO', 'CARGA']:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
        else:
            d[c] = 0

    mov = d['MOVIMENTO_TIPO'].astype(str).str.strip().str.upper() \
        if 'MOVIMENTO_TIPO' in d.columns else pd.Series([], dtype=str)

    pax_local = d['PAX_LOCAL'].sum()
    pax_dom = d['PAX_CONEXAO_DOMESTICO'].sum()
    pax_int = d['PAX_CONEXAO_INTERNACIONAL'].sum()

    return {
        'ATM Total (movimentos)': int(len(d)),
        'ATM Pousos (P)': int((mov == 'P').sum()),
        'ATM Decolagens (D)': int((mov == 'D').sum()),
        'PAX Total': int(pax_local + pax_dom + pax_int),
        'PAX Local': int(pax_local),
        'PAX Conexão Doméstico': int(pax_dom),
        'PAX Conexão Internacional': int(pax_int),
        'Conexões Total': int(pax_dom + pax_int),
        'Carga (kg)': float(d['CARGA'].sum()),
        'Correio (kg)': float(d['CORREIO'].sum()),
    }


def build_fechamento_comparison(resumo_a: dict, resumo_b: dict,
                                nome_a: str, nome_b: str) -> pd.DataFrame:
    """Monta o DataFrame comparativo entre os dois resumos."""
    linhas = []
    for metrica in resumo_a:
        va = resumo_a[metrica]
        vb = resumo_b.get(metrica, 0)
        diff = vb - va
        pct = (diff / va * 100) if va != 0 else (100.0 if diff != 0 else 0.0)
        linhas.append({
            'Métrica': metrica,
            nome_a: va,
            nome_b: vb,
            'Diferença (B−A)': diff,
            'Diferença (%)': round(pct, 2),
            'Status': 'Igual' if diff == 0 else 'Com diferença',
        })
    return pd.DataFrame(linhas)


def render_tab_fechamento(df_a: pd.DataFrame):
    """Renderiza a aba de Fechamento/Conciliação entre dois RIMAs."""
    st.subheader('Fechamento / Conciliação — Comparação entre dois RIMAs')
    st.caption(
        "Compara os totais de ATM (movimentos), passageiros, conexões, carga e "
        "correio entre o arquivo principal (A) e um segundo arquivo (B). "
        "Útil para conciliar versões, períodos ou fontes diferentes do mesmo período."
    )

    arquivo_b = st.file_uploader(
        "Arquivo B (RIMA para comparar)", type="csv", key="fechamento_uploader"
    )

    if arquivo_b is None:
        st.info("⬆️ Envie um segundo arquivo RIMA para comparar com o arquivo principal.")
        return

    try:
        df_b = read_rima_csv(arquivo_b)
    except Exception as e:
        st.error(f"Não foi possível ler o Arquivo B: {e}")
        return

    nome_a = "RIMA A (principal)"
    nome_b = "RIMA B"

    resumo_a = compute_fechamento_summary(df_a)
    resumo_b = compute_fechamento_summary(df_b)
    comp = build_fechamento_comparison(resumo_a, resumo_b, nome_a, nome_b)

    # ── Indicadores de topo (apenas informativos — diferenças são normais) ──
    com_diferenca = int((comp['Status'] == 'Com diferença').sum())
    total_metricas = len(comp)
    col1, col2, col3 = st.columns(3)
    col1.metric('Métricas Comparadas', total_metricas)
    col2.metric('Métricas Iguais', total_metricas - com_diferenca)
    col3.metric('Métricas com Diferença', com_diferenca, delta_color='off')

    if com_diferenca == 0:
        st.info('Os dois RIMAs apresentam os mesmos totais em todas as métricas.')
    else:
        st.info(
            f'{com_diferenca} métrica(s) apresentam diferença entre os arquivos. '
            'Variações de fechamento são esperadas — abaixo estão apenas destacadas para conferência.'
        )

    st.markdown('---')

    # ── Métricas-chave lado a lado (com delta) ─────────────────────────────
    st.write('#### Principais Totais')
    destaques = ['ATM Total (movimentos)', 'PAX Total', 'Conexões Total',
                 'Carga (kg)', 'Correio (kg)']
    cols = st.columns(len(destaques))
    for col, met in zip(cols, destaques):
        va = resumo_a[met]
        vb = resumo_b[met]
        delta = vb - va
        col.metric(met, f'{vb:,.0f}'.replace(',', '.'),
                   f'{delta:+,.0f}'.replace(',', '.') if delta != 0 else None,
                   delta_color='off')

    st.markdown('---')

    # ── Gráfico comparativo ────────────────────────────────────────────────
    fig_df = comp.melt(
        id_vars=['Métrica'], value_vars=[nome_a, nome_b],
        var_name='Arquivo', value_name='Valor'
    )
    fig = px.bar(
        fig_df, x='Métrica', y='Valor', color='Arquivo', barmode='group',
        title='Comparação de Totais por Métrica', template='plotly_white',
        color_discrete_map={nome_a: '#2E86C1', nome_b: '#E67E22'},
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2C3E50'), xaxis_tickangle=-35,
        xaxis_title='Métrica', yaxis_title='Valor', legend_title='Arquivo'
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabela detalhada ───────────────────────────────────────────────────
    st.write('#### Tabela Comparativa Detalhada')

    def _highlight(row):
        # Destaque neutro (azul claro) — diferença não é erro
        cor = 'background-color: #EBF5FB' if row['Status'] == 'Com diferença' else ''
        return [cor] * len(row)

    styled = comp.style.apply(_highlight, axis=1).format({
        nome_a: '{:,.0f}', nome_b: '{:,.0f}',
        'Diferença (B−A)': '{:,.0f}', 'Diferença (%)': '{:+.2f}%',
    })
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # ── Download ───────────────────────────────────────────────────────────
    csv_comp = comp.to_csv(index=False, sep=';').encode('utf-8-sig')
    st.download_button(
        '⬇️ Baixar Fechamento (CSV)',
        data=csv_comp,
        file_name='fechamento_rima.csv',
        mime='text/csv'
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    st.title('Análise de Operações e Passageiros')

    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")

    if uploaded_file is not None:
        # keep_default_na=False + na_values=['']: apenas células realmente vazias
        # viram NaN. Textos como 'N/A', 'NA', 'NULL' são preservados como string
        # (antes o pandas os convertia em nulo e o validador acusava CAMPO VAZIO).
        df = read_rima_csv(uploaded_file)
        df = validate_passenger_count(df)
        df = validate_movement_times(df)
        operations_by_date, passengers_by_date, occupancy_by_aircraft = process_flight_data(df)
        geral_validation_fig, invalid_geral_flights = create_geral_validation_chart(df)
        _, df_with_ponte, _, _ = create_ponte_chart(df)
        df['PONTE_LABEL'] = df_with_ponte['PONTE_LABEL']

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "Operações & Passageiros",
            "Análise de Ocupação",
            "Validação Aviação Geral",
            "Detalhes das Violações",
            "Uso de Ponte de Embarque",
            "✅ Validação de Campos",
            "🔁 Fechamento / Conciliação",     # ← nova aba
        ])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Operações Comerciais", len(df[df['OPERATION_TYPE'] == 'Aviação Comercial']))
            with col2:
                st.metric("Total Operações Aviação Geral", len(df[df['OPERATION_TYPE'] == 'Aviação Geral']))
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
                    ]].sort_values('TOTAL_PAX', ascending=False), hide_index=True
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
                    ]].sort_values(['EXCESSO_PAX', 'CALCO_DATA'], ascending=[False, True]), hide_index=True
                )
            else:
                st.info("Não foram encontradas violações de capacidade.")
            st.write("### Detalhes das Violações de Aviação Geral")
            geral_violations = df[df['GERAL_PAX_VIOLATION']].copy()
            if not geral_violations.empty:
                geral_violations['CALCO_DATA'] = geral_violations['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    geral_violations[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_MARCAS', 'AERONAVE_TIPO',
                        'TOTAL_PAX', 'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values(['TOTAL_PAX', 'CALCO_DATA'], ascending=[False, True]), hide_index=True
                )
                daily_violations = geral_violations.groupby('CALCO_DATA').agg({
                    'VOO_NUMERO': 'count', 'TOTAL_PAX': 'sum',
                    'AERONAVE_MARCAS': lambda x: ', '.join(sorted(set(x)))
                }).reset_index()
                daily_violations.columns = ['Data', 'Número de Voos', 'Total de Passageiros', 'Marcas das Aeronaves']
                st.dataframe(daily_violations.sort_values(['Total de Passageiros', 'Data'], ascending=[False, True]),
                             hide_index=True)
            else:
                st.info("Não foram encontradas violações de aviação geral.")
            st.write("### Detalhes de RPE em Branco")
            rpe_branco_violations = df[df['RPE_BRANCO_VIOLATION']].copy()
            if not rpe_branco_violations.empty:
                rpe_branco_violations['CALCO_DATA'] = rpe_branco_violations['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    rpe_branco_violations[[
                        'CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_MARCAS', 'AERONAVE_TIPO',
                        'SERVICE_TYPE', 'TOTAL_PAX', 'PAX_LOCAL', 'PAX_CONEXAO_DOMESTICO', 'PAX_CONEXAO_INTERNACIONAL'
                    ]].sort_values('CALCO_DATA', ascending=True), hide_index=True
                )
                operator_summary = rpe_branco_violations.groupby(['AERONAVE_OPERADOR', 'SERVICE_TYPE']).agg({
                    'VOO_NUMERO': 'count', 'AERONAVE_MARCAS': lambda x: ', '.join(sorted(set(x)))
                }).reset_index()
                operator_summary.columns = ['Operador', 'Tipo de Serviço', 'Número de Voos', 'Marcas das Aeronaves']
                st.dataframe(operator_summary.sort_values(['Operador', 'Número de Voos'], ascending=[True, False]),
                             hide_index=True)
                total_commercial = len(df[df['AERONAVE_OPERADOR'] != 'GERAL'])
                violation_percentage = (len(rpe_branco_violations) / total_commercial * 100) if total_commercial > 0 else 0
                st.metric("Percentual de Voos Comerciais com RPE em Branco",
                          f"{violation_percentage:.2f}%", delta_color="inverse")
            else:
                st.info("Não foram encontradas violações de RPE em branco.")

        with tab5:
            st.subheader('Uso de Ponte de Embarque (Campo 18 – PONTE_CONECTOR_REMOTO)')
            st.caption(
                "Conforme Portaria nº 2.176/SRA/SIA, de 17.07.2019: "
                "**1** = Ponte de Embarque | **2** = Conector Remoto Acessível | "
                "**3** = Modo Remoto | **4** = Sem Passageiros pelo Terminal"
            )
            filtro_tipo = st.radio("Filtrar por tipo de operação:",
                                   ["Todas as Operações", "Aviação Comercial", "Aviação Geral"],
                                   horizontal=True, key="ponte_filtro")
            if filtro_tipo == "Aviação Geral":
                df_ponte = df[df['OPERATION_TYPE'] == 'Aviação Geral'].copy()
                title_suffix = 'Aviação Geral'
            elif filtro_tipo == "Aviação Comercial":
                df_ponte = df[df['OPERATION_TYPE'] == 'Aviação Comercial'].copy()
                title_suffix = 'Aviação Comercial'
            else:
                df_ponte = df.copy()
                title_suffix = ''
            ponte_fig_filtrado, df_ponte_filtrado, invalid_ponte_count_filtrado, ponte_counts_filtrado = \
                create_ponte_chart(df_ponte, title_suffix=title_suffix)
            total_ops = len(df_ponte)
            col1, col2, col3, col4 = st.columns(4)
            for col, (label, _) in zip(
                [col1, col2, col3, col4],
                [('Ponte de Embarque', ''), ('Conector Remoto Acessível', ''),
                 ('Modo Remoto', ''), ('Sem Passageiros pelo Terminal', '')]
            ):
                count = ponte_counts_filtrado.loc[ponte_counts_filtrado['Modalidade'] == label, 'Quantidade'].values
                count_val = int(count[0]) if len(count) > 0 else 0
                pct = count_val / total_ops * 100 if total_ops > 0 else 0
                with col:
                    st.metric(label, f"{count_val}", f"{pct:.1f}% das operações")
            st.plotly_chart(ponte_fig_filtrado, use_container_width=True)
            st.write("#### Comparativo: Aviação Geral vs. Aviação Comercial")
            st.plotly_chart(create_ponte_by_type_chart(df), use_container_width=True)
            st.write("#### Distribuição por Modalidade")
            ponte_detail = ponte_counts_filtrado.copy()
            ponte_detail['Percentual (%)'] = (ponte_detail['Quantidade'] / total_ops * 100).round(2)
            ponte_detail = ponte_detail.sort_values('Quantidade', ascending=False).reset_index(drop=True)
            st.dataframe(ponte_detail, hide_index=True, use_container_width=True)
            if invalid_ponte_count_filtrado > 0:
                st.warning(
                    f"⚠️ Foram encontrados **{invalid_ponte_count_filtrado}** registros com valor inválido ou ausente "
                    f"no campo PONTE_CONECTOR_REMOTA (esperado: 1, 2, 3 ou 4)."
                )
                invalid_rows = df_ponte_filtrado[df_ponte_filtrado['PONTE_LABEL'].isna()].copy()
                if 'CALCO_DATA' in invalid_rows.columns:
                    invalid_rows['CALCO_DATA'] = invalid_rows['CALCO_DATA'].dt.strftime('%d/%m/%Y')
                st.write("#### Registros com Valor Inválido/Ausente")
                cols_to_show = ['CALCO_DATA', 'VOO_NUMERO', 'AERONAVE_OPERADOR', 'AERONAVE_TIPO', 'PONTE_CONECTOR_REMOTA']
                cols_available = [c for c in cols_to_show if c in invalid_rows.columns]
                st.dataframe(invalid_rows[cols_available].sort_values('CALCO_DATA'), hide_index=True)
            else:
                st.success("✅ Todos os registros possuem valor válido no campo PONTE_CONECTOR_REMOTA.")

        # ── Nova aba 6 ─────────────────────────────────────────────────────
        with tab6:
            render_tab_campos(df)

        # ── Nova aba 7 ─────────────────────────────────────────────────────
        with tab7:
            render_tab_fechamento(df)

        # ── Estatísticas Gerais ────────────────────────────────────────────
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
    st.set_page_config(page_title="Análise de Voos", page_icon="✈️", layout="wide")
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