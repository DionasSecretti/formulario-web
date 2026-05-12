from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime
import re

# ✅ NOVOS IMPORTS GOOGLE
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = "chave_secreta"


# ✅ FUNÇÃO PARA LIMPAR IDS
def limpar_id(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.replace(" ", "_")


# ✅ CONEXÃO COM GOOGLE SHEETS
def conectar_planilha():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_credenciais = os.path.join(base_dir, "credentials.json")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        caminho_credenciais, scope
    )

    cliente = gspread.authorize(creds)

    # ✅ nome EXATO da sua planilha
    return cliente.open("respostas_formulario").sheet1


# ✅ CARREGAR PERGUNTAS DO EXCEL
def carregar_perguntas(nome_formulario="Formulario.xlsx"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_excel = os.path.join(base_dir, nome_formulario)

    df = pd.read_excel(caminho_excel, engine="openpyxl")

    df.columns = df.columns.str.strip().str.lower()
    df = df.fillna("")

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    perguntas = df.to_dict(orient='records')

    mapa_ids = {}

    for p in perguntas:
        p["id"] = limpar_id(p["pergunta"])
        mapa_ids[p["pergunta"]] = p["id"]

    for p in perguntas:
        depende = p.get("depende_de", "")
        p["depende_id"] = mapa_ids.get(depende, "")

    return perguntas


# ✅ ROTA DO FORMULÁRIO
@app.route('/form')
def formulario():
    return render_template(
        'form.html',
        perguntas=carregar_perguntas(),
        titulo="Pesquisa de Clientes"
    )


# ✅ REDIRECIONAMENTO
@app.route('/')
def home():
    return redirect(url_for("formulario"))


# ✅ PROCESSAMENTO DA RESPOSTA
@app.route('/resposta', methods=['POST'])
def resposta():
    perguntas = carregar_perguntas()

    dados = {}
    erros = []

    for p in perguntas:
        campo_id = p["id"]
        valor = request.form.get(campo_id, "").strip()

        obrigatorio = str(p.get("obrigatorio", "")).strip().lower() in ["sim", "true", "1"]
        depende = p.get("depende_id", "")
        cond = str(p.get("valor_condicao", "")).strip().lower()

        # ✅ valida dependência
        if depende:
            valor_dep = request.form.get(depende, "").strip().lower()
            if valor_dep != cond:
                continue

        # ✅ valida obrigatório
        if obrigatorio and valor == "":
            erros.append(f"O campo '{p['pergunta']}' é obrigatório.")

        # ✅ valida lista
        if p["tipo"] == "lista":
            opcoes = p.get("opcoes", "")
            if opcoes:
                lista_opcoes = [o.strip() for o in opcoes.split(";")]
                if valor and valor not in lista_opcoes:
                    erros.append(f"Valor inválido para '{p['pergunta']}'")

        dados[campo_id] = valor

    if erros:
        for erro in erros:
            flash(erro, "erro")
        return redirect(url_for("formulario"))

    # ✅ adicionar data
    dados["data_resposta"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ✅ SALVAR NO GOOGLE SHEETS
    try:
        planilha = conectar_planilha()

        # se primeira vez → cria cabeçalhos
        if not planilha.get_all_values():
            planilha.append_row(list(dados.keys()))

        # adiciona linha
        planilha.append_row(list(dados.values()))

    except Exception as e:
        print("Erro ao salvar no Google Sheets:", e)
        flash("Erro ao salvar resposta. Verifique configuração.", "erro")
        return redirect(url_for("formulario"))

    flash("✅ Resposta salva com sucesso!", "sucesso")
    return redirect(url_for("formulario"))


if __name__ == "__main__":
    app.run(debug=True)
