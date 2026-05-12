from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime
import re

# ✅ Google Sheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = "chave_secreta"


# ✅ LIMPAR ID
def limpar_id(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.replace(" ", "_")


# ✅ CONECTAR GOOGLE SHEETS (SEGURA)
def conectar_planilha():
    try:
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

        return cliente.open("respostas_formulario").sheet1

    except Exception as e:
        print("ERRO AO CONECTAR GOOGLE SHEETS:", e)
        return None  # 👈 MUITO IMPORTANTE (não quebra o app)


# ✅ CARREGAR PERGUNTAS
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


# ✅ FORMULÁRIO
@app.route('/form')
def formulario():
    try:
        perguntas = carregar_perguntas()
        return render_template(
            'form.html',
            perguntas=perguntas,
            titulo="Pesquisa de Clientes"
        )
    except Exception as e:
        return f"Erro ao carregar formulário: {e}"


# ✅ HOME
@app.route('/')
def home():
    return redirect(url_for("formulario"))


# ✅ PROCESSAR RESPOSTA
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

        # ✅ dependência
        if depende:
            valor_dep = request.form.get(depende, "").strip().lower()
            if valor_dep != cond:
                continue

        # ✅ obrigatório
        if obrigatorio and valor == "":
            erros.append(f"O campo '{p['pergunta']}' é obrigatório.")

        # ✅ lista
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

    # ✅ data
    dados["data_resposta"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ✅ SALVAR NO GOOGLE SHEETS (COM PROTEÇÃO)
    planilha = conectar_planilha()

    if planilha:
        try:
            if not planilha.get_all_values():
                planilha.append_row(list(dados.keys()))

            planilha.append_row(list(dados.values()))

            flash("✅ Resposta salva com sucesso!", "sucesso")

        except Exception as e:
            print("ERRO AO SALVAR NA PLANILHA:", e)
            flash("Erro ao salvar no Google Sheets.", "erro")

    else:
        flash("Erro de conexão com Google Sheets.", "erro")

    return redirect(url_for("formulario"))


# ✅ RODAR APP (COMPATÍVEL COM RENDER)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)