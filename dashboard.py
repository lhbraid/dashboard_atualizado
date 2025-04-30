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
import uuid

# Caminhos de diretórios e arquivos
ASSETS_DIR = "assets"
LOGO_PATH = f"{ASSETS_DIR}/logo-dpu.png"
INITIAL_DATA_PATH = "data/dados_iniciais.xlsx"
DATE_COLUMN = 'Data da Instauração'

# Colunas esperadas
COLUMN_MAPPING = {'Oficio': 'Ofício', 'Data da instauração': 'Data da Instauração', 'Materia': 'Matéria'}
REQUIRED_COLUMNS = ['PAJ', 'Unidade', 'Assistido', 'Ofício', 'Pretensão', 'Data da Instauração', 'Matéria', 'Atribuição', 'Defensor', 'Usuário']

# Funções auxiliares
def load_data(file_path):
    try:
        df = pd.read_excel(file_path)
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
        df.dropna(subset=[DATE_COLUMN], inplace=True)
        df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        print("Erro ao carregar dados:", e)
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded))
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors='coerce')
        df.dropna(subset=[DATE_COLUMN], inplace=True)
        df['AnoMês'] = df[DATE_COLUMN].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        print("Erro ao processar upload:", e)
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

# App
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
df_inicial = load_data(INITIAL_DATA_PATH)

app.layout = dbc.Container([
    dcc.Store(id="stored-data", data=df_inicial.to_json(date_format='iso', orient='split')),
    dbc.Row([
        dbc.Col(html.Img(src=app.get_asset_url('logo-dpu.png'), height="60px"), width="auto"),
        dbc.Col(html.H2("Visão geral do SIS - DAT", className="text-center text-primary"), width=True),
    ], className="my-4"),

    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data',
                children=html.Div(['Arraste e solte ou ', html.A('selecione um arquivo Excel')]),
                style={'width': '100%', 'height': '60px', 'lineHeight': '60px',
                       'borderWidth': '1px', 'borderStyle': 'dashed',
                       'borderRadius': '5px', 'textAlign': 'center'},
                multiple=False
            ),
            html.Div(id='upload-status'),
            dbc.Row([
                dbc.Col(dcc.Dropdown(id='filtro-materia', multi=True, placeholder="Matéria"), width=4),
                dbc.Col(dcc.Dropdown(id='filtro-oficio', multi=True, placeholder="Ofício"), width=4),
                dbc.Col(dcc.Dropdown(id='filtro-usuario', multi=True, placeholder="Usuário"), width=4),
            ]),
            dbc.Row([
                dbc.Col(dcc.DatePickerRange(id='filtro-data', display_format='DD/MM/YYYY'), width=12),
            ], className="my-2"),
            dbc.Button("Atualizar Dashboard", id="btn-atualizar", color="primary", className="my-2"),
            dbc.Button("Gerar PDF", id="btn-pdf", color="secondary", className="ms-2"),
            dcc.Download(id="download-pdf")
        ], width=4),

        dbc.Col([
            html.Div(id='total-pajs', className="mb-2"),
            html.Div(id='estatisticas-gerais', className="mb-4"),
            dbc.Row([
                dbc.Col(dcc.Graph(id='grafico-materia'), width=6),
                dbc.Col(dcc.Graph(id='grafico-oficio'), width=6),
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(id='grafico-usuarios'), width=6),
                dbc.Col(dcc.Graph(id='grafico-evolucao'), width=6),
            ]),
            html.H5("Detalhes TOP 10 Usuários"),
            html.Div(id='tabela-top-usuarios'),
        ], width=8)
    ])
], fluid=True)

@app.callback(
    Output('stored-data', 'data'),
    Output('upload-status', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def atualizar_dados(contents, filename):
    if contents:
        df = parse_contents(contents, filename)
        if not df.empty:
            return df.to_json(date_format='iso', orient='split'), f"Arquivo '{filename}' carregado com sucesso."
        else:
            return dash.no_update, "Erro ao carregar o arquivo."
    return dash.no_update, ""

@app.callback(
    [Output('filtro-materia', 'options'),
     Output('filtro-oficio', 'options'),
     Output('filtro-usuario', 'options'),
     Output('filtro-data', 'min_date_allowed'),
     Output('filtro-data', 'max_date_allowed')],
    Input('stored-data', 'data')
)
def popular_filtros(json_data):
    df = pd.read_json(json_data, orient='split')
    return (
        [{'label': i, 'value': i} for i in sorted(df['Matéria'].unique())],
        [{'label': i, 'value': i} for i in sorted(df['Ofício'].unique())],
        [{'label': i, 'value': i} for i in sorted(df['Usuário'].unique())],
        df[DATE_COLUMN].min().date(),
        df[DATE_COLUMN].max().date()
    )

@app.callback(
    Output('total-pajs', 'children'),
    Output('estatisticas-gerais', 'children'),
    Output('grafico-materia', 'figure'),
    Output('grafico-oficio', 'figure'),
    Output('grafico-usuarios', 'figure'),
    Output('grafico-evolucao', 'figure'),
    Output('tabela-top-usuarios', 'children'),
    Input('btn-atualizar', 'n_clicks'),
    State('stored-data', 'data'),
    State('filtro-materia', 'value'),
    State('filtro-oficio', 'value'),
    State('filtro-usuario', 'value'),
    State('filtro-data', 'start_date'),
    State('filtro-data', 'end_date')
)
def atualizar_dashboard(_, json_data, materias, oficios, usuarios, start, end):
    df = pd.read_json(json_data, orient='split')
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])

    if materias: df = df[df['Matéria'].isin(materias)]
    if oficios: df = df[df['Ofício'].isin(oficios)]
    if usuarios: df = df[df['Usuário'].isin(usuarios)]
    if start: df = df[df[DATE_COLUMN] >= pd.to_datetime(start)]
    if end: df = df[df[DATE_COLUMN] <= pd.to_datetime(end)]

    total = len(df)
    media = df['PAJ'].nunique() / df['Usuário'].nunique() if not df.empty else 0
    mediana = df['PAJ'].nunique() // 2
    variancia = df['Usuário'].value_counts().var()

    estatisticas = dbc.Table([
        html.Thead(html.Tr([html.Th("Média"), html.Th("Mediana"), html.Th("Variância")])),
        html.Tbody(html.Tr([
            html.Td(f"{media:.1f}"), html.Td(mediana), html.Td(f"{variancia:.2f}" if not np.isnan(variancia) else "0")
        ]))
    ], bordered=True)

    pie_materia = px.pie(df, names='Matéria', title="Distribuição por Matéria", hole=0.4)
    pie_materia.update_traces(textinfo='percent+value')

    pie_oficio = px.pie(df, names='Ofício', title="Distribuição por Ofício", hole=0.4)
    pie_oficio.update_traces(textinfo='percent+value')

    top_usuarios = df['Usuário'].value_counts().nlargest(10).reset_index()
    top_usuarios.columns = ['Usuário', 'PAJs']
    top_usuarios['Desvio da Média'] = top_usuarios['PAJs'] - media
    grafico_usuarios = px.bar(top_usuarios, x='Usuário', y='PAJs', text='Desvio da Média', title="Top 10 Usuários")

    evolucao = df.groupby('AnoMês').size().reset_index(name='PAJs')
    grafico_evolucao = px.line(evolucao, x='AnoMês', y='PAJs', markers=True, title="Evolução de PAJs")

    tabela = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in top_usuarios.columns],
        data=top_usuarios.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center'}
    )

    return f"Total PAJs: {total}", estatisticas, pie_materia, pie_oficio, grafico_usuarios, grafico_evolucao, tabela

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)

