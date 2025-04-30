# -*- coding: utf-8 -*-
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
import weasyprint
import os

# --- Constantes e Configurações Iniciais ---
UPLOAD_DIR = "/home/ubuntu/upload"
ASSETS_DIR = "/home/ubuntu/dashboard_dpu/assets"
LOGO_PATH = f"{ASSETS_DIR}/logo-dpu.png"
# Ajuste aqui para o seu usuário/branch/projeto no GitHub
INITIAL_DATA_PATH = "https://raw.githubusercontent.com/seu-usuario/seu-repo/main/data/initial_data.xlsx"

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

def load_data(path):
    try:
        df = pd.read_excel(path)
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Colunas ausentes: {missing}")
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
        df.dropna(subset=[DATE_COLUMN], inplace=True)
        df['Ano'] = df[DATE_COLUMN].dt.year
        df['Mês'] = df[DATE_COLUMN].dt.month
        df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        print(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Ano','Mês','AnoMês'])

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded))
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Colunas ausentes no upload: {missing}")
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
        df.dropna(subset=[DATE_COLUMN], inplace=True)
        df['Ano'] = df[DATE_COLUMN].dt.year
        df['Mês'] = df[DATE_COLUMN].dt.month
        df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        print(f"Erro ao processar upload {filename}: {e}")
        return None

def create_chart_image(df, chart_type, top_n=10):
    buf = io.BytesIO()
    plt.close('all')
    sns.set_style("whitegrid")
    if chart_type == 'materia':
        plt.figure(figsize=(6,4))
        order = df['Matéria'].value_counts().index
        ax = sns.countplot(y='Matéria', data=df, order=order, palette="pastel")
        plt.title("Distribuição por Matéria")
        for p in ax.patches:
            count = p.get_width()
            pct = count / len(df)
            ax.annotate(f"{count} ({pct:.1%})",
                        (p.get_width(), p.get_y() + p.get_height()/2),
                        va='center')
    elif chart_type == 'oficio':
        plt.figure(figsize=(6,4))
        order = df['Ofício'].value_counts().index
        ax = sns.countplot(y='Ofício', data=df, order=order, palette="Set2")
        plt.title("Distribuição por Ofício")
        for p in ax.patches:
            count = p.get_width()
            pct = count / len(df)
            ax.annotate(f"{count} ({pct:.1%})",
                        (p.get_width(), p.get_y() + p.get_height()/2),
                        va='center')
    elif chart_type == 'usuarios':
        plt.figure(figsize=(6,4))
        counts = df['Usuário'].value_counts().nlargest(top_n)
        ax = sns.barplot(x=counts.values, y=counts.index, orient='h', palette="viridis")
        plt.title(f"TOP {top_n} Usuários por Nº de PAJs")
        for p in ax.patches:
            ax.annotate(f"{int(p.get_width())}",
                        (p.get_width(), p.get_y() + p.get_height()/2),
                        va='center')
    elif chart_type == 'evolucao':
        plt.figure(figsize=(6,4))
        evo = df.groupby('AnoMês').size().reset_index(name='Contagem')
        ax = sns.lineplot(x='AnoMês', y='Contagem', data=evo, marker='o')
        plt.title("Evolução Mensal de PAJs")
        plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def generate_report_html_base64(df, top_n):
    if df.empty:
        return "<h1>Relatório DPU</h1><p>Nenhum dado.</p>"
    imgs = {t: create_chart_image(df, t, top_n) for t in ['materia','oficio','usuarios','evolucao']}
    total = len(df)
    user_counts = df['Usuário'].value_counts()
    mean_ = user_counts.mean()
    median_ = user_counts.median()
    var_ = user_counts.var()
    stats_html = f"""
    <table border="1" cellpadding="4">
      <tr><th>Métrica</th><th>Valor</th></tr>
      <tr><td>Média PAJs/Usuário</td><td>{mean_:.2f}</td></tr>
      <tr><td>Mediana PAJs/Usuário</td><td>{median_:.2f}</td></tr>
      <tr><td>Variância PAJs/Usuário</td><td>{var_:.2f}</td></tr>
    </table>
    """
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Relatório DPU</title></head><body>
<h1>Relatório DPU - Visão Geral SIS</h1>
<p>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
<p><strong>Total PAJs:</strong> {total}</p>
{stats_html}
<h2>Distribuição por Matéria</h2><img src="data:image/png;base64,{imgs['materia']}"><br>
<h2>Distribuição por Ofício</h2><img src="data:image/png;base64,{imgs['oficio']}"><br>
<h2>TOP {top_n} Usuários</h2><img src="data:image/png;base64,{imgs['usuarios']}"><br>
<h2>Evolução Mensal de PAJs</h2><img src="data:image/png;base64,{imgs['evolucao']}"><br>
</body></html>"""
    return html

# --- Inicialização do App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True, assets_folder=ASSETS_DIR)
server = app.server

df_initial = load_data(INITIAL_DATA_PATH)

app.layout = dbc.Container(fluid=True, children=[
    dcc.Store(id='stored-data', data=df_initial.to_json(date_format='iso', orient='split')),
    dbc.Row([
        dbc.Col(html.Img(src=app.get_asset_url('logo-dpu.png'), height="60px"), width="auto"),
        dbc.Col(html.H2("Visão geral do SIS - DAT"), width=True),
    ], align="center", className="mb-4"),
    dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Div("Atualizar Dados:"),
                dcc.Upload(id='upload-data',
                           children=html.Div(['Arraste ou ', html.A('Selecione um Excel')]),
                           style={'border':'1px dashed #ccc','padding':'10px'},
                           multiple=False),
                html.Div(id='output-data-upload-status')
            ], width=12, lg=3),
            dbc.Col(html.Div("Filtros:"), width=12, lg=9),
        ]),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id='filtro-materia', placeholder="Matéria", multi=True), width=6, md=3),
            dbc.Col(dcc.Dropdown(id='filtro-oficio', placeholder="Ofício", multi=True), width=6, md=3),
            dbc.Col(dcc.Dropdown(id='filtro-usuario', placeholder="Usuário", multi=True), width=6, md=3),
            dbc.Col(dcc.RadioItems(id='date-filter-type', options=[
                                      {'label':'Dia Único','value':'single'},
                                      {'label':'Período','value':'range'}],
                                   value='single', inline=True), width=6, md=3),
        ]),
        dbc.Row(dbc.Col(html.Div(id='date-filter-inputs'), width=12)),
    ]))), className="mb-4"),
    dbc.Row([
        dbc.Col([dbc.Card(dbc.CardBody(id='total-pajs')),
                 dbc.Card(dbc.CardBody(id='stats-card'),
                          style={'width':'12cm','height':'9cm','marginTop':'1rem'})],
                width=12, lg=3),
        dbc.Col(html.Img(id='grafico-materia', style={'width':'100%'}), width=12, md=6, lg=4),
        dbc.Col(html.Img(id='grafico-oficio', style={'width':'100%'}), width=12, md=6, lg=5),
    ], className="mb-4"),
    dbc.Row([
        dbc.Col(html.Img(id='grafico-usuarios', style={'width':'100%'}), width=12, lg=7),
        dbc.Col(html.Img(id='grafico-evolucao', style={'width':'100%'}), width=12, lg=5),
    ], className="mb-4"),
    dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
        html.H5("Detalhes TOP 10 Usuários"), html.Div(id='tabela-top-usuarios'),
        dbc.Button("Gerar PDF", id='btn-pdf', color='primary'),
        dcc.Download(id='download-pdf')
    ]))), className="mb-4"),
])

# --- Callbacks ---
@app.callback(
    Output('output-data-upload-status','children'),
    Output('stored-data','data'),
    Input('upload-data','contents'),
    State('upload-data','filename')
)
def update_data(contents, filename):
    if contents:
        df = parse_contents(contents, filename)
        if df is not None:
            return html.Div(f'Arquivo {filename} carregado.', className='text-success'), df.to_json(date_format='iso', orient='split')
    return "", dash.no_update

@app.callback(
    Output('date-filter-inputs','children'),
    Input('date-filter-type','value'),
    State('stored-data','data')
)
def render_date_filter(ftype, data):
    if not data:
        return ""
    df = pd.read_json(data, orient='split')
    min_d, max_d = df[DATE_COLUMN].min().date(), df[DATE_COLUMN].max().date()
    if ftype == 'single':
        return dcc.DatePickerSingle(id='filtro-data-single', min_date_allowed=min_d,
                                    max_date_allowed=max_d, display_format='DD/MM/YYYY', clearable=True)
    return dcc.DatePickerRange(id='filtro-data', min_date_allowed=min_d,
                               max_date_allowed=max_d, display_format='DD/MM/YYYY', clearable=True)

@app.callback(
    Output('filtro-materia','options'),
    Output('filtro-oficio','options'),
    Output('filtro-usuario','options'),
    Input('stored-data','data')
)
def update_filters(data):
    if not data:
        return [], [], []
    df = pd.read_json(data, orient='split')
    return (
        [{'label':i,'value':i} for i in sorted(df['Matéria'].unique())],
        [{'label':i,'value':i} for i in sorted(df['Ofício'].unique())],
        [{'label':i,'value':i} for i in sorted(df['Usuário'].unique())]
    )

@app.callback(
    Output('total-pajs','children'),
    Output('stats-card','children'),
    Output('grafico-materia','src'),
    Output('grafico-oficio','src'),
    Output('grafico-usuarios','src'),
    Output('grafico-evolucao','src'),
    Output('tabela-top-usuarios','children'),
    Input('stored-data','data'),
    Input('filtro-materia','value'),
    Input('filtro-oficio','value'),
    Input('filtro-usuario','value'),
    Input('date-filter-type','value'),
    Input('filtro-data-single','date'),
    Input('filtro-data','start_date'),
    Input('filtro-data','end_date'),
    Input('top-n-usuarios','value'),
)
def update_dashboard(data, mat, ofi, usr, ftype, sdate, start, end, top_n):
    if not data:
        return ["",""], "", "", "", "", "", ""
    df = pd.read_json(data, orient='split')
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
    # filtragem
    if ftype=='single' and sdate:
        df = df[df[DATE_COLUMN]==pd.to_datetime(sdate)]
    elif ftype=='range' and start and end:
        df = df[(df[DATE_COLUMN]>=pd.to_datetime(start))&(df[DATE_COLUMN]<=pd.to_datetime(end))]
    if mat:
        df = df[df['Matéria'].isin(mat)]
    if ofi:
        df = df[df['Ofício'].isin(ofi)]
    if usr:
        df = df[df['Usuário'].isin(usr)]
    total = len(df)
    counts = df['Usuário'].value_counts()
    mean_, med_, var_ = counts.mean(), counts.median(), counts.var()
    card = [html.H4("Total PAJs Instaurados"), html.H2(f"{total}", className="text-primary")]
    stats_table = html.Table([
        html.Tr([html.Th("Métrica"), html.Th("Valor")]),
        html.Tr([html.Td("Média"), html.Td(f"{mean_:.2f}")]),
        html.Tr([html.Td("Mediana"), html.Td(f"{med_:.2f}")]),
        html.Tr([html.Td("Variância"), html.Td(f"{var_:.2f}")])
    ], style={'width':'100%','textAlign':'left'})
    img_m = "data:image/png;base64,"+create_chart_image(df,'materia')
    img_o = "data:image/png;base64,"+create_chart_image(df,'oficio')
    img_u = "data:image/png;base64,"+create_chart_image(df,'usuarios', int(top_n or 10))
    img_e = "data:image/png;base64,"+create_chart_image(df,'evolucao')
    top10 = counts.nlargest(int(top_n or 10)).rename_axis('Usuário').reset_index(name='Quantidade PAJs')
    overall = counts.mean()
    top10['Variância'] = (top10['Quantidade PAJs']-overall)**2
    table = dbc.Table.from_dataframe(top10, striped=True, bordered=True, hover=True)
    return card, stats_table, img_m, img_o, img_u, img_e, table

@app.callback(
    Output('download-pdf','data'),
    Input('btn-pdf','n_clicks'),
    State('stored-data','data'),
    State('top-n-usuarios','value'),
    State('filtro-data','start_date'),
    State('filtro-data','end_date'),
    prevent_initial_call=True
)
def generate_pdf(n, data, top_n, start, end):
    if not data:
        return dash.no_update
    df = pd.read_json(data, orient='split')
    html = generate_report_html_base64(df, int(top_n or 10))
    pdf = weasyprint.HTML(string=html).write_pdf()
    return dcc.send_bytes(pdf, f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

if __name__ == '__main__':
    port = int(os.environ.get("PORT",8050))
    app.run(host='0.0.0.0', port=port, debug=False)


