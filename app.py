from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "chave_secreta"


def limpar_id(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.replace(" ", "_")


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


# ✅ NOVA ROTA (URL AMIGÁVEL)
@app.route('/form')
def formulario():
    return render_template(
        'form.html',
        perguntas=carregar_perguntas(),
        titulo="Pesquisa de Clientes"
    )


# ✅ (opcional) ainda mantém raiz funcionando
@app.route('/')
def home():
    return redirect(url_for("formulario"))


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

        if depende:
            valor_dep = request.form.get(depende, "").strip().lower()
            if valor_dep != cond:
                continue

        if obrigatorio and valor == "":
            erros.append(f"O campo '{p['pergunta']}' é obrigatório.")

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

    dados["data_resposta"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_respostas = os.path.join(base_dir, "respostas.xlsx")

    df_novo = pd.DataFrame([dados])

    if os.path.exists(caminho_respostas):
        df = pd.read_excel(caminho_respostas, engine="openpyxl")
        df = pd.concat([df, df_novo], ignore_index=True)
    else:
        df = df_novo

    df.to_excel(caminho_respostas, index=False)

    flash("✅ Resposta salva com sucesso!", "sucesso")
    return redirect(url_for("formulario"))


if __name__ == "__main__":
    app.run(debug=True)