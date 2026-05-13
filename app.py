from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime
import re
import psycopg2

app = Flask(__name__)
app.secret_key = "chave_secreta"


# ==========================================
# ✅ CONEXÃO COM BANCO (ROBUSTA)
# ==========================================
def conectar_banco():
    try:
        url = os.environ.get("DATABASE_URL")

        if not url:
            print("DATABASE_URL NÃO CONFIGURADO!")
            return None

        # Ajuste padrão do Render
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        conn = psycopg2.connect(url)
        return conn

    except Exception as e:
        print("Erro ao conectar no banco:", e)
        return None


# ==========================================
# ✅ CRIAR TABELA (SEM TRAVAR APP)
# ==========================================
def criar_tabela():
    try:
        conn = conectar_banco()
        if not conn:
            return

        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            id SERIAL PRIMARY KEY,
            dados TEXT,
            data_resposta TEXT
        )
        """)

        conn.commit()
        conn.close()

        print("Tabela verificada/criada com sucesso.")

    except Exception as e:
        print("Erro ao criar tabela:", e)


# ✅ NÃO TRAVAR O APP NA INICIALIZAÇÃO
try:
    criar_tabela()
except Exception as e:
    print("Erro na inicialização:", e)


# ==========================================
# ✅ LIMPAR ID
# ==========================================
def limpar_id(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.replace(" ", "_")


# ==========================================
# ✅ CARREGAR PERGUNTAS (COM PROTEÇÃO)
# ==========================================
def carregar_perguntas(nome_formulario="Formulario.xlsx"):
    try:
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

    except Exception as e:
        print("Erro ao carregar perguntas:", e)
        return []


# ==========================================
# ✅ FORMULÁRIO
# ==========================================
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


# ==========================================
# ✅ HOME
# ==========================================
@app.route('/')
def home():
    return redirect(url_for("formulario"))


# ==========================================
# ✅ PROCESSAR RESPOSTA
# ==========================================
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

    # ==========================================
    # ✅ SALVAR NO BANCO
    # ==========================================
    conn = conectar_banco()

    if conn:
        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO respostas (dados, data_resposta) VALUES (%s, %s)",
                (str(dados), dados["data_resposta"])
            )

            conn.commit()
            conn.close()

            flash("✅ Resposta salva no banco com sucesso!", "sucesso")

        except Exception as e:
            print("Erro ao salvar:", e)
            flash("Erro ao salvar no banco.", "erro")

    else:
        flash("Erro de conexão com o banco.", "erro")

    return redirect(url_for("formulario"))


# ==========================================
# ✅ HEALTH CHECK (IMPORTANTE PARA DEBUG)
# ==========================================
@app.route('/status')
def status():
    return "APP ONLINE ✅"


# ==========================================
# ✅ RODAR APP
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)