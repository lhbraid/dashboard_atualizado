# -*- coding: utf-8 -*-
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import io
import base64
from datetime import datetime
import weasyprint
import os
import uuid  # Para nomes de arquivos temporários

# --- Constantes e Configurações Iniciais ---
UPLOAD_DIR = "/home/ubuntu/upload"
ASSETS_DIR = "/home/ubuntu/dashboard_dpu/assets"
LOGO_PATH = f"{ASSETS_DIR}/logo-dpu.png"
# Carregar direto do GitHub (substitua 'seu-usuario' e 'seu-repo' pelos valores corretos)
INITIAL_DATA_PATH = "https://raw.githubusercontent.com/seu-usuario/seu-repo/main/data/initial_data.xlsx"
TEMP_DIR = "/tmp"  # Diretório para imagens temporárias

# Colunas esperadas e renomeação
COLUMN_MAPPING = {
    'Oficio': 'Ofício',
    'Data da instauração': 'Data da Instauração',
    'Materia': 'Matéria'
}
REQUIRED_COLUMNS = [
    'PAJ', 'Unidade', 'Assistido', 'Ofício', 'Pretensão',
    'Data da Instauração', 'Matéria', 'Atribuição', 'Defensor', 'Usuário'
]
DATE_COLUMN = 'Data da Instauração'

# --- Funções Auxiliares ---
def load_data(file_path):
    """Carrega dados de um arquivo Excel, renomeia colunas e trata datas."""
    try:
        df = pd.read_excel(file_path)
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Colunas ausentes no arquivo: {', '.join(missing_cols)}")
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
        df.dropna(subset=[DATE_COLUMN], inplace=True)
        df['Ano'] = df[DATE_COLUMN].dt.year
        df['Mês'] = df[DATE_COLUMN].dt.month
        df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        print(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Ano', 'Mês', 'AnoMês'])

def parse_contents(contents, filename):
    """Processa o conteúdo do arquivo carregado."""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded))
            df.rename(columns=COLUMN_MAPPING, inplace=True)
            missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Colunas ausentes no arquivo carregado: {', '.join(missing_cols)}")
            df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
            df.dropna(subset=[DATE_COLUMN], inplace=True)
            df['Ano'] = df[DATE_COLUMN].dt.year
            df['Mês'] = df[DATE_COLUMN].dt.month
            df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
            return df
        else:
            raise ValueError("Formato de arquivo não suportado. Use .xlsx ou .xls")
    except Exception as e:
        print(f"Erro ao processar o arquivo carregado {filename}: {e}")
        return None

def generate_report_html_base64(dff, top_n):
    """Gera o conteúdo HTML para o relatório PDF com base nos dados filtrados."""
    if dff.empty:
        return "<h1>Relatório DPU</h1><p>Nenhum dado corresponde aos filtros selecionados.</p>"

    total_pajs = len(dff)
    # Gráficos com contagem e percentual
    materia_counts = dff['Matéria'].value_counts()
    fig_materia = px.pie(
        materia_counts, values=materia_counts.values, names=materia_counts.index,
        title="Distribuição por Matéria", hole=.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_materia.update_traces(textinfo='label+percent+value', texttemplate='%{label}<br>%{percent:.1%}<br>%{value}', pull=[0.05]*len(materia_counts))
    fig_materia.update_layout(showlegend=False, margin=dict(t=50,b=0,l=0,r=0))

    oficio_counts = dff['Ofício'].value_counts()
    fig_oficio = px.pie(
        oficio_counts, values=oficio_counts.values, names=oficio_counts.index,
        title="Distribuição por Ofício", hole=.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_oficio.update_traces(textinfo='label+percent+value', texttemplate='%{label}<br>%{percent:.1%}<br>%{value}', pull=[0.05]*len(oficio_counts))
    fig_oficio.update_layout(showlegend=False, margin=dict(t=50,b=0,l=0,r=0))

    # TOP usuários e evolução
    user_counts = dff['Usuário'].value_counts().nlargest(top_n)
    fig_usuarios = px.bar(
        user_counts, x=user_counts.index, y=user_counts.values, text_auto=True,
        title=f"TOP {top_n} Usuários por Nº de PAJs",
        labels={'x':'Usuário','y':'Nº PAJs'},
        color_discrete_sequence=px.colors.qualitative.Vivid
    )
    fig_usuarios.update_layout(xaxis_tickangle=-45, margin=dict(t=50,b=100,l=0,r=0))

    evolucao = dff.groupby('AnoMês').size().reset_index(name='Contagem').sort_values('AnoMês')
    fig_evolucao = px.line(
        evolucao, x='AnoMês', y='Contagem', markers=True,
        title="Evolução Mensal de PAJs",
        labels={'AnoMês':'Mês/Ano','Contagem':'Nº PAJs'}
    )
    fig_evolucao.update_layout(margin=dict(t=50,b=0,l=0,r=0))

    # Tabela Top10 com variância
    top10 = dff['Usuário'].value_counts().nlargest(10).rename_axis('Usuário').reset_index(name='Quantidade PAJs')
    overall_mean = dff['Usuário'].value_counts().mean()
    top10['Variância'] = (top10['Quantidade PAJs'] - overall_mean)**2
    tabela_html = top10.to_html(index=False, classes='table table-striped', border=0)

    # Geração de imagens em base64
    img_base64 = {}
    for name, fig in [('materia', fig_materia), ('oficio', fig_oficio), ('usuarios', fig_usuarios), ('evolucao', fig_evolucao)]:
        try:
            img_bytes = fig.to_image(format="png", scale=2)
            img_base64[name] = base64.b64encode(img_bytes).decode()
        except Exception as e:
            print(f"Erro ao gerar imagem {name}: {e}")
            img_base64[name] = None

    encoded_logo = base64.b64encode(open(LOGO_PATH,'rb').read()).decode()

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Relatório DPU - Visão Geral SIS</title>
<style>
body {{ font-family: sans-serif; margin:20px }}
h1,h2,h3 {{ color: #004080 }}
.chart-container {{ display:flex; flex-wrap:wrap; gap:20px; margin-bottom:30px; page-break-inside:avoid }}
.chart {{ flex:1 1 45%; min-width:300px; border:1px solid #ccc; padding:10px; box-shadow:2px 2px 5px #eee; text-align:center }}
.full-width-chart {{ flex:1 1 100% }}
.total-box {{ background-color:#e7f3ff; border-left:6px solid #2196F3; padding:15px; margin-bottom:20px; font-size:1.2em }}
</style></head><body>
<h1><img src="data:image/png;base64,{encoded_logo}" height="40px" style="vertical-align:middle;margin-right:10px">Relatório DPU - Visão Geral SIS</h1>
<p>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
<div class="total-box"><strong>Total PAJs Instaurados: {total_pajs}</strong></div>
<div class="chart-container">
  <div class="chart"><h2>Distribuição por Matéria</h2><img src="data:image/png;base64,{img_base64.get('materia','')}"></div>
  <div class="chart"><h2>Distribuição por Ofício</h2><img src="data:image/png;base64,{img_base64.get('oficio','')}"></div>
</div>
<div class="chart-container full-width-chart"><h2>TOP {top_n} Usuários</h2><img src="data:image/png;base64,{img_base64.get('usuarios','')}"></div>
<div class="chart-container full-width-chart"><h2>Evolução Mensal de PAJs</h2><img src="data:image/png;base64,{img_base64.get('evolucao','')}"></div>
<div><h2>Detalhes TOP 10 Usuários</h2>{tabela_html}</div>
</body></html>"""
    return html

# --- Inicialização do App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True, assets_folder=ASSETS_DIR)
server = app.server

# --- Carregamento Inicial dos Dados ---
df_inicial = load_data(INITIAL_DATA_PATH)

# --- Layout ---
app.layout = dbc.Container(fluid=True, className="dbc", children=[
    dcc.Store(id='stored-data', data=df_inicial.to_json(date_format='iso', orient='split') if not df_inicial.empty else None),
    dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div("Atualizar Dados:"),
                                dcc.Upload(
                                    id='upload-data',
                                    children=html.Div(['Arraste ou ', html.A('Selecione um Arquivo Excel')]),
                                    style={'border': '1px dashed #ccc', 'padding': '10px'},
                                    multiple=False
                                ),
                                html.Div(id='output-data-upload-status')
                            ], width=12, lg=3),
                            dbc.Col(html.Div("Filtros:"), width=12, lg=9)
                        ]),
                        dbc.Row([
                            dbc.Col(dcc.Dropdown(id='filtro-materia', placeholder="Matéria", multi=True), width=6, md=3),
                            dbc.Col(dcc.Dropdown(id='filtro-oficio', placeholder="Ofício", multi=True), width=6, md=3),
                            dbc.Col(dcc.Dropdown(id='filtro-usuario', placeholder="Usuário", multi=True), width=6, md=3),
                            dbc.Col(dcc.RadioItems(
                                id='date-filter-type',
                                options=[
                                    {'label': 'Dia Único', 'value': 'single'},
                                    {'label': 'Período', 'value': 'range'}
                                ],
                                value='single',
                                inline=True
                            ), width=6, md=3)
                        ]),
                        dbc.Row(
                            dbc.Col(html.Div(id='date-filter-inputs'), width=12)
                        )
                    ])
                ),
                width=12
            )
        ],
        className="mb-4"
    ),
    dbc.Row([
        dbc.Col([dbc.Card(dbc.CardBody(id='total-pajs')), dbc.Card(dbc.CardBody(id='stats-card'), style={'width':'12cm','height':'9cm','marginTop':'1rem'})], width=12, lg=3),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id='grafico-materia'))), width=12, md=6, lg=4),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id='grafico-oficio'))), width=12, md=6, lg=5)
    ], className="mb-4"),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([dbc.Row([dbc.Col(html.H5("PAJs por Usuário"), width=8), dbc.Col(dcc.Dropdown(id='top-n-usuarios', options=[{'label':'TOP 10','value':10},{'label':'TOP 20','value':20}], value=10), width=4)], align="center"), dcc.Graph(id='grafico-usuarios')])), width=12, lg=7),
        dbc.Col(dbc.Card(dbc.CardBody([html.H5("Evolução de PAJs por Mês"), dcc.Graph(id='grafico-evolucao')])), width=12, lg=5)
    ], className="mb-4"),
    dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([html.H5("Detalhes TOP 10 Usuários"), html.Div(id='tabela-top-usuarios'), dbc.Button("Gerar PDF", id='btn-pdf', color='primary'), dcc.Download(id='download-pdf')]))), width=12)
])

# --- Callbacks ---
@app.callback(Output('date-filter-inputs','children'),
              Input('date-filter-type','value'),
              State('filtro-data','min_date_allowed'),
              State('filtro-data','max_date_allowed'))
def render_date_filter(filter_type, min_date, max_date):
    if filter_type=='single':
        return dcc.DatePickerSingle(id='filtro-data-single', min_date_allowed=min_date, max_date_allowed=max_date, display_format='DD/MM/YYYY', clearable=True)
    else:
        return dcc.DatePickerRange(id='filtro-data', min_date_allowed=min_date, max_date_allowed=max_date, display_format='DD/MM/YYYY', clearable=True)

@app.callback(Output('stored-data','data'),
              Output('output-data-upload-status','children'),
              Input('upload-data','contents'),
              State('upload-data','filename'))
def update_output(contents, filename):
    if contents:
        df_new = parse_contents(contents, filename)
        if df_new is not None and not df_new.empty:
            return df_new.to_json(date_format='iso', orient='split'), html.Div(f'Arquivo "{filename}" carregado com sucesso.', className='text-success')
        else:
            return dash.no_update, html.Div(f'Falha ao carregar "{filename}".', className='text-danger')
    return dash.no_update, ""

@app.callback(Output('filtro-materia','options'),
              Output('filtro-oficio','options'),
              Output('filtro-usuario','options'),
              Output('filtro-data','min_date_allowed'),
              Output('filtro-data','max_date_allowed'),
              Output('filtro-data','initial_visible_month'),
              Input('stored-data','data'))
def update_filter_options(jsonified_data):
    if not jsonified_data:
        return [], [], [], None, None, None
    df = pd.read_json(jsonified_data, orient='split')
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
    return (
        [{'label':i,'value':i} for i in sorted(df['Matéria'].unique())],
        [{'label':i,'value':i} for i in sorted(df['Ofício'].unique())],
        [{'label':i,'value':i} for i in sorted(df['Usuário'].unique())],
        df[DATE_COLUMN].min().date(),
        df[DATE_COLUMN].max().date(),
        df[DATE_COLUMN].min().date()
    )

@app.callback(
    Output('total-pajs','children'),
    Output('stats-card','children'),
    Output('grafico-materia','figure'),
    Output('grafico-oficio','figure'),
    Output('grafico-usuarios','figure'),
    Output('grafico-evolucao','figure'),
    Output('tabela-top-usuarios','children'),
    Input('stored-data','data'),
    Input('filtro-materia','value'),
    Input('filtro-oficio','value'),
    Input('filtro-usuario','value'),
    Input('date-filter-type','value'),
    Input('filtro-data-single','date'),
    Input('filtro-data','start_date'),
    Input('filtro-data','end_date'),
    Input('top-n-usuarios','value')
)
def update_dashboard(jsonified_data, mat_sel, ofi_sel, usr_sel, filter_type, single_date, start_date, end_date, top_n):
    if not jsonified_data:
        empty_fig = go.Figure().update_layout(template='plotly_white', annotations=[dict(text="Sem dados", showarrow=False)])
        return "", "", empty_fig, empty_fig, empty_fig, empty_fig, ""
    dff = pd.read_json(jsonified_data, orient='split')
    if dff.empty:
        empty_fig = go.Figure().update_layout(template='plotly_white', annotations=[dict(text="Sem dados", showarrow=False)])
        return "", "", empty_fig, empty_fig, empty_fig, empty_fig, ""
    dff[DATE_COLUMN] = pd.to_datetime(dff[DATE_COLUMN])
    # Filtragem de data
    if filter_type=='single' and single_date:
        sel = pd.to_datetime(single_date)
        dff = dff[dff[DATE_COLUMN]==sel]
    else:
        if start_date and end_date:
            dff = dff[(dff[DATE_COLUMN]>=pd.to_datetime(start_date))&(dff[DATE_COLUMN]<=pd.to_datetime(end_date))]
        elif start_date:
            dff = dff[dff[DATE_COLUMN]>=pd.to_datetime(start_date)]
        elif end_date:
            dff = dff[dff[DATE_COLUMN]<=pd.to_datetime(end_date)]
    # Outros filtros
    if mat_sel:
        dff = dff[dff['Matéria'].isin(mat_sel)]
    if ofi_sel:
        dff = dff[dff['Ofício'].isin(ofi_sel)]
    if usr_sel:
        dff = dff[dff['Usuário'].isin(usr_sel)]
    if dff.empty:
        empty_fig = go.Figure().update_layout(template='plotly_white', annotations=[dict(text="Nenhum dado corresponde", showarrow=False)])
        return "Total PAJs: 0", "", empty_fig, empty_fig, empty_fig, empty_fig, "Nenhum dado"
    # Métricas
    total_pajs = len(dff)
    card = [html.H4("Total PAJs Instaurados"), html.H2(f"{total_pajs}", className="text-primary")]
    counts = dff['Usuário'].value_counts()
    mean_, median_, var_ = counts.mean(), counts.median(), counts.var()
    stats = html.Table([
        html.Tr([html.Th("Métrica"), html.Th("Valor")]),
        html.Tr([html.Td("Média PAJs/Usuário"), html.Td(f"{mean_:.2f}")]),
        html.Tr([html.Td("Mediana PAJs/Usuário"), html.Td(f"{median_:.2f}")]),
        html.Tr([html.Td("Variância PAJs/Usuário"), html.Td(f"{var_:.2f}")])
    ], style={'width':'100%','textAlign':'left'})
    # Gráficos
    # (reutilizar lógica de generate_report_html_base64 para criar figuras aqui...)
    materia_counts = dff['Matéria'].value_counts()
    fig1 = px.pie(materia_counts, values=materia_counts.values, names=materia_counts.index, hole=.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig1.update_traces(textinfo='label+percent+value', texttemplate='%{label}<br>%{percent:.1%}<br>%{value}')
    fig1.update_layout(showlegend=False, margin=dict(t=50,b=0,l=0,r=0))
    oficio_counts = dff['Ofício'].value_counts()
    fig2 = px.pie(oficio_counts, values=oficio_counts.values, names=oficio_counts.index, hole=.4, color_discrete_sequence=px.colors.qualitative.Set2)
    fig2.update_traces(textinfo='label+percent+value', texttemplate='%{label}<br>%{percent:.1%}<br>%{value}')
    fig2.update_layout(showlegend=False, margin=dict(t=50,b=0,l=0,r=0))
    user_counts = dff['Usuário'].value_counts().nlargest(int(top_n))
    fig3 = px.bar(user_counts, x=user_counts.index, y=user_counts.values, text_auto=True)
    fig3.update_layout(xaxis_tickangle=-45, margin=dict(t=50,b=100,l=0,r=0))
    evo = dff.groupby('AnoMês').size().reset_index(name='Contagem').sort_values('AnoMês')
    fig4 = px.line(evo, x='AnoMês', y='Contagem', markers=True)
    fig4.update_layout(margin=dict(t=50,b=0,l=0,r=0))
    # Tabela Top10 com variância
    top10 = counts.nlargest(10).rename_axis('Usuário').reset_index(name='Quantidade PAJs')
    overall = counts.mean()
    top10['Variância'] = (top10['Quantidade PAJs'] - overall)**2
    table = dash_table.DataTable(
        columns=[{"name":c,"id":c} for c in top10.columns],
        data=top10.to_dict('records'),
        style_table={'overflowX':'auto'}
    )
    return card, stats, fig1, fig2, fig3, fig4, table

@app.callback(Output("download-pdf","data"),
              Input("btn-pdf","n_clicks"),
              State('stored-data','data'),
              State('filtro-materia','value'),
              State('filtro-oficio','value'),
              State('filtro-usuario','value'),
              State('date-filter-type','value'),
              State('filtro-data-single','date'),
              State('filtro-data','start_date'),
              State('filtro-data','end_date'),
              State('top-n-usuarios','value'),
              prevent_initial_call=True)
def generate_pdf(n_clicks, jsonified_data, mat_sel, ofi_sel, usr_sel, filter_type, single_date, start_date, end_date, top_n):
    if not n_clicks or not jsonified_data:
        return dash.no_update
    dff = pd.read_json(jsonified_data, orient='split')
    dff[DATE_COLUMN] = pd.to_datetime(dff[DATE_COLUMN])
    # Filtragem similar ao update_dashboard...
    if filter_type=='single' and single_date:
        dff = dff[dff[DATE_COLUMN]==pd.to_datetime(single_date)]
    else:
        if start_date and end_date:
            dff = dff[(dff[DATE_COLUMN]>=pd.to_datetime(start_date))&(dff[DATE_COLUMN]<=pd.to_datetime(end_date))]
        elif start_date:
            dff = dff[dff[DATE_COLUMN]>=pd.to_datetime(start_date)]
        elif end_date:
            dff = dff[dff[DATE_COLUMN]<=pd.to_datetime(end_date)]
    if mat_sel:
        dff = dff[dff['Matéria'].isin(mat_sel)]
    if ofi_sel:
        dff = dff[dff['Ofício'].isin(ofi_sel)]
    if usr_sel:
        dff = dff[dff['Usuário'].isin(usr_sel)]
    html = generate_report_html_base64(dff, int(top_n))
    pdf = weasyprint.HTML(string=html).write_pdf()
    return dcc.send_bytes(pdf, f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

if __name__=='__main__':
    port = int(os.environ.get("PORT",8050))
    app.run(debug=False, host='0.0.0.0', port=port)


