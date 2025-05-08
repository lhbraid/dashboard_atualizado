import os
from flask import Flask
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd

# ─── Servidor Flask ────────────────────────────────────────────────────────────
server = Flask(__name__)

# ─── Dash app ───────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname='/',                         # monta o Dash na raiz
    external_stylesheets=[dbc.themes.BOOTSTRAP]    # bootstrap para layout
)

# ─── Carrega dados ─────────────────────────────────────────────────────────────
# Define aqui a URL "raw" do seu Excel no GitHub ou via variável de ambiente
DATA_URL = os.getenv(
    'INITIAL_DATA_PATH',
    'https://raw.githubusercontent.com/seu-usuario/seu-repo/main/data/Dados%20SIS%20compilado%20-%2024.04.25.xlsx'
)

# Tenta baixar e ler o Excel
try:
    df = pd.read_excel(DATA_URL)
except Exception as e:
    # Se falhar, cria um df vazio de fallback
    print(f"Erro ao carregar dados: {e}")
    df = pd.DataFrame()

# ─── Layout ─────────────────────────────────────────────────────────────────────
app.layout = dbc.Container([
    # Navbar/Cabeçalho
    dbc.NavbarSimple(
        brand="Visão Geral do SIS - DAT",
        brand_href="/",
        color="primary",
        dark=True,
        fluid=True,
    ),
    html.Br(),

    # Exemplo de filtro de data
    dbc.Row([
        dbc.Col(dcc.DatePickerRange(
            id='date-picker',
            min_date_allowed=df['dt_venda'].min() if 'dt_venda' in df.columns else None,
            max_date_allowed=df['dt_entrega'].max() if 'dt_entrega' in df.columns else None,
            start_date=df['dt_venda'].min() if 'dt_venda' in df.columns else None,
            end_date=df['dt_entrega'].max() if 'dt_entrega' in df.columns else None,
            display_format='DD/MM/YYYY'
        ), width=6),
    ]),
    html.Hr(),

    # Área de gráficos
    dbc.Row([
        dbc.Col(dcc.Graph(id='grafico-exemplo'), width=12),
    ]),

    # Mensagem de erro/data vazia
    html.Div(id='msg-sem-dados', className='text-danger')
], fluid=True)


# ─── Callbacks ──────────────────────────────────────────────────────────────────
@app.callback(
    dash.dependencies.Output('grafico-exemplo', 'figure'),
    dash.dependencies.Output('msg-sem-dados', 'children'),
    dash.dependencies.Input('date-picker', 'start_date'),
    dash.dependencies.Input('date-picker', 'end_date'),
)
def atualizar_grafico(start_date, end_date):
    if df.empty:
        return {}, "Nenhum dado disponível para exibir."
    # Filtra por data, supondo colunas dt_venda do tipo datetime
    mask = (df['dt_venda'] >= start_date) & (df['dt_venda'] <= end_date)
    dff = df.loc[mask]

    if dff.empty:
        return {}, "Não há registros no período selecionado."

    # Exemplo simples: contagem por categoria (ajuste conforme sua coluna)
    serie = dff['Categoria'].value_counts()
    fig = {
        'data': [{
            'x': serie.index.tolist(),
            'y': serie.values.tolist(),
            'type': 'bar'
        }],
        'layout': {
            'title': 'Exemplo: Contagem por Categoria'
        }
    }
    return fig, ""


# ─── Execução local ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Apenas para dev local; em produção use Gunicorn conforme abaixo
    app.run_server(
        debug=True,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8050))
    )
