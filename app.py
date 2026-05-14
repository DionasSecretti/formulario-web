from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import psycopg2
import io
import json

app = Flask(__name__)
app.secret_key = "chave_secreta"

# 🔐 CREDENCIAIS
USUARIO_ADMIN = "admin"
SENHA_ADMIN = "12345"
SENHA_LIMPEZA = "abc123"

# 🌎 TIMEZONE
TIMEZONE = ZoneInfo("America/Sao_Paulo")

# ==========================================
def agora_formatado():
    return datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M")

# ==========================================
def conectar_banco():
    try:
        url = os.environ.get("DATABASE_URL")

        if not url:
            print("DATABASE_URL NÃO CONFIGURADO!")
            return None

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        return psycopg2.connect(url, connect_timeout=5)

    except Exception as e:
        print("Erro ao conectar no banco:", e)
        return None

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
    except Exception as e:
        print("Erro ao criar tabela:", e)

try:
    criar_tabela()
except:
    pass

# ==========================================
def limpar_id(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.replace(" ", "_")

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
@app.route('/form')
def formulario():
    return render_template(
        'form.html',
        perguntas=carregar_perguntas(),
        titulo="Pesquisa de Clientes"
    )

@app.route('/')
def home():
    return redirect(url_for("formulario"))

# ==========================================
@app.route('/resposta', methods=['POST'])
def resposta():
    perguntas = carregar_perguntas()

    dados = {}
    erros = []

    for p in perguntas:
        campo_id = p["id"]
        valor = request.form.get(campo_id, "").strip()

        obrigatorio = str(p.get("obrigatorio", "")).lower() in ["sim", "true", "1"]
        depende = p.get("depende_id", "")
        cond = str(p.get("valor_condicao", "")).lower()

        if depende:
            valor_dep = request.form.get(depende, "").lower()
            if valor_dep != cond:
                continue

        if obrigatorio and not valor:
            erros.append(f"O campo '{p['pergunta']}' é obrigatório.")

        if p["tipo"] == "lista":
            opcoes = p.get("opcoes", "")
            if opcoes:
                lista = [o.strip() for o in opcoes.split(";")]
                if valor and valor not in lista:
                    erros.append(f"Valor inválido para '{p['pergunta']}'")

        dados[campo_id] = valor

    if erros:
        for erro in erros:
            flash(erro, "erro")
        return redirect(url_for("formulario"))

    dados["data_resposta"] = agora_formatado()

    conn = conectar_banco()

    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO respostas (dados, data_resposta) VALUES (%s, %s)",
            (json.dumps(dados), dados["data_resposta"])
        )
        conn.commit()
        conn.close()
        flash("✅ Resposta salva com sucesso!", "sucesso")
    else:
        flash("Erro no banco", "erro")

    return redirect(url_for("formulario"))

# ==========================================
@app.route('/admin')
def admin():
    usuario = request.args.get("usuario")
    senha = request.args.get("senha")

    if usuario != USUARIO_ADMIN or senha != SENHA_ADMIN:
        return "⛔ Acesso não autorizado"

    return '''
    <html>
    <head>
        <title>Painel Administrativo</title>
        <style>
            body {
                font-family: Arial;
                background: #f4f6f9;
                padding: 40px;
            }

            .container {
                max-width: 500px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 6px 18px rgba(0,0,0,0.1);
            }

            h2, h3 {
                text-align: center;
            }

            .acoes {
                display: flex;
                gap: 10px;
                margin-bottom: 25px;
            }

            .botao {
                flex: 1;
                padding: 12px;
                text-align: center;
                border-radius: 6px;
                text-decoration: none;
                font-weight: bold;
                color: white;
            }

            .exportar { background: #1e73e8; }
            .ver { background: #28a745; }

            input {
                width: 100%;
                padding: 10px;
                margin-top: 8px;
                border-radius: 6px;
                border: 1px solid #ccc;
                box-sizing: border-box;
            }

            button {
                margin-top: 15px;
                width: 100%;
                padding: 12px;
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }
        </style>
    </head>

    <body>
        <div class="container">

            <h2>⚙️ Painel Administrativo</h2>

            <div class="acoes">
                <a class="botao exportar" href="/exportar">📥 Exportar Excel</a>
                <a class="botao ver" href="/respostas?senha=12345">📋 Ver Respostas</a>
            </div>

            <h3>🗑 Limpar banco</h3>

            <form method="post" action="/limpar">
                <input type="password" name="senha_limpeza" placeholder="Senha de confirmação">

                <button onclick="return confirm('Tem certeza que deseja apagar TODOS os dados?')">
                    ⚠️ Limpar todos os dados
                </button>
            </form>

        </div>
    </body>
    </html>
    '''

# ==========================================
@app.route('/limpar', methods=['POST'])
def limpar_dados():
    senha = request.form.get("senha_limpeza")

    if senha != SENHA_LIMPEZA:
        return "⛔ Senha incorreta"

    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE respostas RESTART IDENTITY")
        conn.commit()
        conn.close()
        return "✅ Banco limpo com sucesso!"
    except Exception as e:
        return f"Erro ao limpar: {e}"

# ==========================================
@app.route('/exportar', methods=['GET', 'POST'])
def exportar():
    if request.method == 'POST':
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")

        if usuario != USUARIO_ADMIN or senha != SENHA_ADMIN:
            return "⛔ Acesso não autorizado"

        try:
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("SELECT dados, data_resposta FROM respostas")
            registros = cursor.fetchall()
            conn.close()

            lista = []

            for r in registros:
                try:
                    dados = json.loads(r[0])
                    dados["data_resposta"] = r[1]
                    lista.append(dados)
                except:
                    continue

            df = pd.DataFrame(lista)

            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name="respostas_formulario.xlsx"
            )

        except Exception as e:
            return f"Erro ao exportar: {e}"

    return '''
        <h2>🔐 Acesso para Exportar</h2>
        <form method="post">
            <input type="text" name="usuario" placeholder="Usuário"><br><br>
            <input type="password" name="senha" placeholder="Senha"><br><br>
            <button type="submit">Baixar Excel</button>
        </form>
    '''

# ==========================================
@app.route('/status')
def status():
    return "APP ONLINE ✅"

# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)