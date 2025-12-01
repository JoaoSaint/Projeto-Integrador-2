import requests
from datetime import datetime, timedelta
try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:
    # fallback, se necessário, instala pytz e use: ZoneInfo = None
    ZoneInfo = None

from flask import Flask, request, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from utils import contar_itens_lista
import os
import tempfile
import shutil
from collections import Counter
from sqlalchemy import or_

# --- Caminhos dos bancos (template e runtime) ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Banco "real" (dados de ocorrências) que já vem populado
TEMPLATE_MAIN_DB = os.path.join(BASE_DIR, "instance", "dados.db")
# Banco de usuários usado em /login
TEMPLATE_AUTH_DB = os.path.join(BASE_DIR, "usuarios.db")

if os.getenv("VERCEL"):
    # No Vercel: usar /tmp (área gravável e efêmera)
    tmp_dir = tempfile.gettempdir()
    RUNTIME_MAIN_DB = os.path.join(tmp_dir, "dados_runtime.db")
    RUNTIME_AUTH_DB = os.path.join(tmp_dir, "usuarios_runtime.db")

    # Se ainda não existe a cópia, copiar do template só uma vez
    if not os.path.exists(RUNTIME_MAIN_DB):
        shutil.copy(TEMPLATE_MAIN_DB, RUNTIME_MAIN_DB)

    if not os.path.exists(RUNTIME_AUTH_DB):
        shutil.copy(TEMPLATE_AUTH_DB, RUNTIME_AUTH_DB)
else:
    # Local: usar diretamente os arquivos do projeto
    RUNTIME_MAIN_DB = TEMPLATE_MAIN_DB
    RUNTIME_AUTH_DB = TEMPLATE_AUTH_DB

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

# SQLAlchemy sempre aponta para o banco "runtime"
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{RUNTIME_MAIN_DB}"
db = SQLAlchemy(app)

# Quantidade por página para listagem
PER_PAGE = 20

WEATHER_ICON_MAP = {
    "sem_risco": "sem_risco.svg",
    "nevoeiro": "nevoeiro.svg",
    "chuva_leve": "chuva_leve.svg",
    "chuva_moderada": "chuva_moderada.svg",
    "chuva_forte": "chuva_forte.svg",
    "tempestade": "tempestade.svg",
    "vento_forte": "vento_forte.svg",
    "vento_extremo": "vento_extremo.svg",
    "neve": "neve.svg",
    "desconhecido": "desconhecido.svg",
}


def classify_weather_risk(weather_code, precip, wind):
    """Retorna (descricao, icon_key, severidade) para a combinação fornecida."""
    descricao = "Condição estável"
    icon_key = "sem_risco"
    severidade = 0

    if weather_code in {45, 48}:
        descricao = "Nevoeiro isolado"
        icon_key = "nevoeiro"
        severidade = max(severidade, 2)
    elif weather_code in {51, 53, 55, 56, 57}:
        descricao = "Garoa leve"
        icon_key = "chuva_leve"
        severidade = max(severidade, 2)
    elif weather_code in {61, 63, 65, 66, 67}:
        descricao = "Chuva moderada"
        icon_key = "chuva_moderada"
        severidade = max(severidade, 3)
    elif weather_code in {80, 81, 82}:
        descricao = "Chuva forte"
        icon_key = "chuva_forte"
        severidade = max(severidade, 4)
    elif weather_code in {71, 73, 75, 77, 85, 86}:
        descricao = "Precipitação invernal"
        icon_key = "neve"
        severidade = max(severidade, 3)
    elif weather_code in {95, 96, 99}:
        descricao = "Tempestade com raios"
        icon_key = "tempestade"
        severidade = max(severidade, 5)

    if precip is not None:
        if precip >= 8:
            descricao = "Chuva intensa prevista"
            icon_key = "chuva_forte"
            severidade = max(severidade, 4)
        elif precip >= 3:
            descricao = "Chuva moderada prevista"
            icon_key = "chuva_moderada"
            severidade = max(severidade, 3)
        elif precip >= 0.5 and severidade < 2:
            descricao = "Possibilidade de garoa"
            icon_key = "chuva_leve"
            severidade = max(severidade, 2)

    if wind is not None:
        if wind >= 65:
            descricao = "Risco extremo de ventos"
            icon_key = "vento_extremo"
            severidade = max(severidade, 5)
        elif wind >= 45 and severidade < 5:
            descricao = "Ventos fortes previstos"
            icon_key = "vento_forte"
            severidade = max(severidade, 4)

    if icon_key not in WEATHER_ICON_MAP:
        icon_key = "desconhecido"

    return descricao, icon_key, severidade

class Entrada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emitente = db.Column(db.String(40), nullable=False)
    classificação = db.Column(db.String(15), nullable=False)
    empresa = db.Column(db.String(15), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    local = db.Column(db.String(20), nullable=False)
    observação = db.Column(db.String(150), nullable=False)
    ação = db.Column(db.String(150), nullable=False)                   # Ação imediata
    class_sst = db.Column(db.String(50), nullable=True)              # Apenas um? sst/ambiental
    class_ambiental = db.Column(db.String(50), nullable=True)         # Apenas um? sst/ambiental
    causa = db.Column(db.String(300), nullable=True)                   # Deve ser múltipla escolha ?
    parecer = db.Column(db.String(100), nullable=True)               #    Discutir necessidade e utilidade <<<< ("Estabelecer ações posteriores")
    num_ordem_man = db.Column(db.String(20), nullable=True)            # Número da Ordem de Manutenção
    obs_sprocedencia = db.Column(db.String(20), nullable=True)         # Observação sem procedência
    obs_justificativa = db.Column(db.String(20), nullable=True)         # Justificativa 
    multipla_condição = db.Column(db.String(60), nullable=True)       # Multipla condição insegura
    multipla_comportamento = db.Column(db.String(60), nullable=True)       # Multipla Comportamento Inseguro
    multipla_ambiental = db.Column(db.String(60), nullable=True)       # Multipla Ocorrência Ambiental
    funcionario = db.Column(db.String(20), nullable=True)

with app.app_context():
    db.create_all()

def get_weather_today(lat, lon, timezone_str='America/Sao_Paulo'):
    """
    Consulta Open-Meteo e retorna dados de risco do dia atual,
    incluindo um resumo, métricas diárias e previsões por hora.
    """
    try:
        hoje = datetime.now().date()
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
            "&hourly=precipitation,weathercode,windspeed_10m"
            "&forecast_days=1"
            f"&timezone={timezone_str}"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        d = data.get('daily', {})
        if not d or not d.get('time'):
            return None

        # Encontrar índice do dia atual
        idx = None
        for i, dia_str in enumerate(d['time']):
            if dia_str == hoje.isoformat():
                idx = i
                break
        if idx is None:
            return None

        temp_max = d['temperature_2m_max'][idx]
        temp_min = d['temperature_2m_min'][idx]
        precip = d['precipitation_sum'][idx]
        wind = d['wind_speed_10m_max'][idx]

        hourly = data.get('hourly', {})
        times = hourly.get('time', [])
        precip_h = hourly.get('precipitation', [])
        wind_h = hourly.get('windspeed_10m', [])
        codes_h = hourly.get('weathercode', [])

        tzinfo = ZoneInfo(timezone_str) if ZoneInfo else None
        if tzinfo:
            now_local = datetime.now(tzinfo)
            now_local_naive = now_local.replace(tzinfo=None)
        else:
            now_local = datetime.utcnow()
            now_local_naive = now_local

        hourly_entries = []
        for t, p, w, c in zip(times, precip_h, wind_h, codes_h):
            try:
                dt = datetime.fromisoformat(t)
            except ValueError:
                continue
            if dt.date() != hoje:
                continue
            if dt < now_local_naive - timedelta(hours=1):
                continue

            risk_desc, icon_key, severity = classify_weather_risk(c, p, w)
            icon_file = WEATHER_ICON_MAP.get(icon_key, WEATHER_ICON_MAP['desconhecido'])
            hourly_entries.append({
                "dt": dt,
                "time": dt.strftime("%H:%M"),
                "precip": round(p, 1) if p is not None else 0,
                "wind": round(w, 1) if w is not None else 0,
                "risk": risk_desc,
                "icon_key": icon_key,
                "icon": icon_file,
                "severity": severity,
            })

        hourly_entries.sort(key=lambda item: item['dt'])
        hours_to_show = []
        overall_severity = -1
        summary_icon_key = 'sem_risco'
        summary_texts = []

        for entry in hourly_entries[:6]:
            hours_to_show.append({
                "time": entry['time'],
                "precip": entry['precip'],
                "wind": entry['wind'],
                "risk": entry['risk'],
                "icon": entry['icon'],
                "icon_key": entry['icon_key'],
            })
            if entry['severity'] > overall_severity:
                overall_severity = entry['severity']
                summary_icon_key = entry['icon_key']
            if entry['icon_key'] != 'sem_risco':
                summary_texts.append(entry['risk'])

        summary_texts = list(dict.fromkeys(summary_texts))  # remove duplicados preservando ordem

        if summary_texts:
            summary = " / ".join(summary_texts)
        else:
            summary = "Sem riscos significativos nas próximas horas"

        summary_icon = WEATHER_ICON_MAP.get(summary_icon_key, WEATHER_ICON_MAP['desconhecido'])

        return {
            "summary": summary,
            "summary_icon": summary_icon,
            "risk_icon": summary_icon_key,
            "temp_max": round(temp_max, 1),
            "temp_min": round(temp_min, 1),
            "precip": round(precip, 1),
            "wind": round(wind, 1),
            "hours": hours_to_show,
        }

    except Exception:
        return None

def init_auth_db():
    # Usa o mesmo caminho definido para o banco de usuários em runtime
    with sqlite3.connect(RUNTIME_AUTH_DB) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        """)

        # Usuário padrão de teste
        c.execute(
            "INSERT OR IGNORE INTO usuarios (id, username, password) VALUES (1, 'teste', '1234')"
        )
        conn.commit()


@app.before_first_request
def setup_dbs():
    # Garante que a tabela de usuários exista no runtime DB
    init_auth_db()

# Tela Inicial
@app.route('/')
def index():
    LATITUDE = -21.3607
    LONGITUDE = -48.2282
    weather = get_weather_today(LATITUDE, LONGITUDE)
    return render_template('index.html', weather=weather)




# Tela de Login para o SSMA 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["username"]
        senha = request.form["password"]
        with sqlite3.connect(RUNTIME_AUTH_DB) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM usuarios WHERE username=? AND password=?",
                (usuario, senha),
            )
            user = c.fetchone()
            if user:
                session["logado"] = True
                return redirect(url_for("ssma"))
        return "Login inválido!"
    return render_template("login.html")

# Página exclusiva do SSMA 
@app.route("/ssma", methods=["GET", "POST"])             
def ssma():
    if not session.get("logado"):
        return redirect(url_for("login"))

    # Submissão de dados (mesmo comportamento anterior)
    if request.method == "POST":
        ids = request.form.getlist("id_list")
        for entrada_id in ids:
            entrada = Entrada.query.get(entrada_id)
            if entrada:
                entrada.class_sst = request.form.get(f"class_sst_{entrada_id}", "")
                entrada.class_ambiental = request.form.get(f"class_ambiental_{entrada_id}", "")
                entrada.causa = ', '.join(request.form.getlist(f"causa_{entrada_id}"))
                entrada.parecer = request.form.get(f"parecer_{entrada_id}", "")
                entrada.num_ordem_man = request.form.get(f"num_ordem_man_{entrada_id}", "")
                entrada.obs_sprocedencia = request.form.get(f"obs_sprocedencia_{entrada_id}", "")
                entrada.obs_justificativa = request.form.get(f"obs_justificativa_{entrada_id}", "")
                entrada.multipla_condição = ', '.join(request.form.getlist(f"multipla_condição_{entrada_id}"))
                entrada.multipla_comportamento = ', '.join(request.form.getlist(f"multipla_comportamento_{entrada_id}"))
                entrada.multipla_ambiental = ', '.join(request.form.getlist(f"multipla_ambiental_{entrada_id}"))
                entrada.funcionario = request.form.get(f"funcionario{entrada_id}", "")
        db.session.commit()
        return redirect(url_for("ssma"))

    # Paginação
    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    per_page = 10  # quantidade de formulários por página

    # Query ordenando pelo ID decrescente (mais recentes primeiro)
    entradas_pag = Entrada.query.order_by(Entrada.id.asc()).paginate(page=page, per_page=per_page)

    return render_template("ssma.html",
                           entradas=entradas_pag.items,
                           page=page,
                           total_pages=entradas_pag.pages)


# Formulário de abertura (com paginação)
@app.route("/abertura", methods=["GET", "POST"])
def abertura():
    if request.method == 'POST':
        # gravação da nova entrada
        emitente = request.form['emitente']
        classificação = request.form['classificação']
        empresa = request.form['empresa']
        data = datetime.strptime(request.form['data'], "%Y-%m-%d").date()
        hora = datetime.strptime(request.form['hora'], "%H:%M").time()
        local = request.form['local']
        observação = request.form['observação']
        ação = request.form['ação']
        class_sst = request.form.get('class_sst')
        class_ambiental = request.form.get('class_ambiental')
        causa = ','.join(request.form.getlist('causa'))
        parecer = request.form.get('parecer')
        num_ordem_man = request.form.get('num_ordem_man')
        obs_sprocedencia = request.form.get('obs_sprocedencia')
        obs_justificativa = request.form.get('obs_justificativa')
        multipla_condição = ','.join(request.form.getlist('multipla_condição'))
        multipla_comportamento = ','.join(request.form.getlist('multipla_comportamento'))
        multipla_ambiental = ','.join(request.form.getlist('multipla_ambiental'))
        funcionario = request.form.get('funcionario')

        nova_entrada = Entrada(
            emitente=emitente,
            classificação=classificação,
            empresa=empresa,
            data=data,
            hora=hora,
            local=local,
            observação=observação,
            ação=ação,
            class_sst=class_sst,
            class_ambiental=class_ambiental,
            causa=causa,
            parecer=parecer,
            num_ordem_man=num_ordem_man,
            obs_sprocedencia=obs_sprocedencia,
            obs_justificativa=obs_justificativa,
            multipla_condição=multipla_condição,
            multipla_comportamento=multipla_comportamento,
            multipla_ambiental=multipla_ambiental,
            funcionario=funcionario,
        )
        db.session.add(nova_entrada)
        db.session.commit()
        # Post/Redirect/Get para evitar re-submissão do form
        return redirect(url_for('abertura', page=1))

    # leitura com paginação: mostrará os últimos registros (ordenados por id DESC)
    page = request.args.get('page', 1, type=int)
    # usamos order_by id desc para trazer os mais recentes primeiro
    pagination = Entrada.query.order_by(Entrada.id.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    entradas = pagination.items  # lista de registros desta página
    total_pages = pagination.pages or 1

    return render_template('abertura.html',
                           entradas=entradas,
                           page=page,
                           per_page=PER_PAGE,
                           total_pages=total_pages)


# Gráficos, teste
@app.route('/graficos')
def graficos():
    def preparar_dados(contagem):
        etiquetas = list(contagem.keys())
        valores = [contagem[label] for label in etiquetas]
        return {"labels": etiquetas, "counts": valores}

    filtros_args = request.args

    consulta = Entrada.query

    filtros_selecionados = {
        "emitente": filtros_args.get("emitente", "").strip(),
        "causa": filtros_args.get("causa", "").strip(),
        "local": filtros_args.get("local", "").strip(),
        "data_inicio": filtros_args.get("data_inicio", "").strip(),
        "data_fim": filtros_args.get("data_fim", "").strip(),
        "mes": filtros_args.get("mes", "").strip(),
        "ano": filtros_args.get("ano", "").strip(),
        "empresa": filtros_args.get("empresa", "").strip(),
        "descricao": filtros_args.get("descricao", "").strip(),
        "acao": filtros_args.get("acao", "").strip(),
        "class_sst": filtros_args.get("class_sst", "").strip(),
        "class_ambiental": filtros_args.get("class_ambiental", "").strip(),
        "parecer": filtros_args.get("parecer", "").strip(),
        "justificativa": filtros_args.get("justificativa", "").strip(),
        "procedencia": filtros_args.get("procedencia", "").strip(),
        "funcionario": filtros_args.get("funcionario", "").strip(),
        "hora_min": filtros_args.get("hora_min", "").strip(),
        "hora_max": filtros_args.get("hora_max", "").strip(),
        "condicao": [valor.strip() for valor in filtros_args.getlist("condicao") if valor.strip()],
        "comportamento": [valor.strip() for valor in filtros_args.getlist("comportamento") if valor.strip()],
        "ambiental": [valor.strip() for valor in filtros_args.getlist("ambiental") if valor.strip()],
    }

    if filtros_selecionados["data_inicio"]:
        try:
            data_inicio = datetime.strptime(filtros_selecionados["data_inicio"], "%Y-%m-%d").date()
            consulta = consulta.filter(Entrada.data >= data_inicio)
        except ValueError:
            filtros_selecionados["data_inicio"] = ""

    if filtros_selecionados["data_fim"]:
        try:
            data_fim = datetime.strptime(filtros_selecionados["data_fim"], "%Y-%m-%d").date()
            consulta = consulta.filter(Entrada.data <= data_fim)
        except ValueError:
            filtros_selecionados["data_fim"] = ""

    if filtros_selecionados["mes"]:
        try:
            mes_int = int(filtros_selecionados["mes"])
            if 1 <= mes_int <= 12:
                filtros_selecionados["mes"] = f"{mes_int:02d}"
                consulta = consulta.filter(db.func.strftime("%m", Entrada.data) == filtros_selecionados["mes"])
            else:
                filtros_selecionados["mes"] = ""
        except ValueError:
            filtros_selecionados["mes"] = ""

    if filtros_selecionados["ano"]:
        try:
            ano_int = int(filtros_selecionados["ano"])
            consulta = consulta.filter(db.func.strftime("%Y", Entrada.data) == f"{ano_int:04d}")
            filtros_selecionados["ano"] = f"{ano_int:04d}"
        except ValueError:
            filtros_selecionados["ano"] = ""

    if filtros_selecionados["emitente"]:
        consulta = consulta.filter(Entrada.emitente == filtros_selecionados["emitente"])

    if filtros_selecionados["local"]:
        consulta = consulta.filter(Entrada.local == filtros_selecionados["local"])

    if filtros_selecionados["causa"]:
        consulta = consulta.filter(Entrada.causa.isnot(None)).filter(Entrada.causa.contains(filtros_selecionados["causa"]))

    if filtros_selecionados["empresa"]:
        consulta = consulta.filter(Entrada.empresa == filtros_selecionados["empresa"])

    if filtros_selecionados["descricao"]:
        consulta = consulta.filter(Entrada.observação.isnot(None)).filter(Entrada.observação.contains(filtros_selecionados["descricao"]))

    if filtros_selecionados["acao"]:
        consulta = consulta.filter(Entrada.ação.isnot(None)).filter(Entrada.ação.contains(filtros_selecionados["acao"]))

    if filtros_selecionados["class_sst"]:
        consulta = consulta.filter(Entrada.class_sst == filtros_selecionados["class_sst"])

    if filtros_selecionados["class_ambiental"]:
        consulta = consulta.filter(Entrada.class_ambiental == filtros_selecionados["class_ambiental"])

    if filtros_selecionados["parecer"]:
        consulta = consulta.filter(Entrada.parecer == filtros_selecionados["parecer"])

    if filtros_selecionados["justificativa"]:
        consulta = consulta.filter(Entrada.obs_justificativa == filtros_selecionados["justificativa"])

    if filtros_selecionados["procedencia"]:
        consulta = consulta.filter(Entrada.obs_sprocedencia == filtros_selecionados["procedencia"])

    if filtros_selecionados["funcionario"]:
        consulta = consulta.filter(Entrada.funcionario == filtros_selecionados["funcionario"])

    if filtros_selecionados["hora_min"]:
        try:
            hora_min = datetime.strptime(filtros_selecionados["hora_min"], "%H:%M").time()
            consulta = consulta.filter(Entrada.hora >= hora_min)
        except ValueError:
            filtros_selecionados["hora_min"] = ""

    if filtros_selecionados["hora_max"]:
        try:
            hora_max = datetime.strptime(filtros_selecionados["hora_max"], "%H:%M").time()
            consulta = consulta.filter(Entrada.hora <= hora_max)
        except ValueError:
            filtros_selecionados["hora_max"] = ""

    if filtros_selecionados["condicao"]:
        condicoes = [Entrada.multipla_condição.contains(valor) for valor in filtros_selecionados["condicao"]]
        if condicoes:
            consulta = consulta.filter(Entrada.multipla_condição.isnot(None)).filter(or_(*condicoes))

    if filtros_selecionados["comportamento"]:
        comportamentos = [Entrada.multipla_comportamento.contains(valor) for valor in filtros_selecionados["comportamento"]]
        if comportamentos:
            consulta = consulta.filter(Entrada.multipla_comportamento.isnot(None)).filter(or_(*comportamentos))

    if filtros_selecionados["ambiental"]:
        ambientais = [Entrada.multipla_ambiental.contains(valor) for valor in filtros_selecionados["ambiental"]]
        if ambientais:
            consulta = consulta.filter(Entrada.multipla_ambiental.isnot(None)).filter(or_(*ambientais))

    entradas_filtradas = consulta.all()

    contagem_class = contar_itens_lista(entradas_filtradas, 'classificação')
    contagem_local = contar_itens_lista(entradas_filtradas, 'local')
    contagem_agentes = contar_itens_lista(entradas_filtradas, 'causa')
    contagem_multipla_condição = contar_itens_lista(entradas_filtradas, 'multipla_condição')
    contagem_multipla_comportamento = contar_itens_lista(entradas_filtradas, 'multipla_comportamento')
    contagem_multipla_ambiental = contar_itens_lista(entradas_filtradas, 'multipla_ambiental')
    contagem_class_sst = contar_itens_lista(entradas_filtradas, 'class_sst')

    contagem_diaria = Counter()
    for entrada in entradas_filtradas:
        if entrada.data:
            contagem_diaria[entrada.data] += 1

    contagem_por_dia = {
        data.strftime("%d/%m/%Y"): contagem_diaria[data]
        for data in sorted(contagem_diaria)
    }

    emitentes_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.emitente)
        .filter(Entrada.emitente.isnot(None))
        .distinct()
        .order_by(Entrada.emitente)
        .all()
        if resultado[0]
    ]

    causas_brutas = (
        db.session.query(Entrada.causa)
        .filter(Entrada.causa.isnot(None))
        .all()
    )
    causas_disponiveis = sorted(
        {
            item.strip()
            for (valor,) in causas_brutas
            if valor
            for item in valor.split(',')
            if item.strip()
        }
    )

    locais_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.local)
        .filter(Entrada.local.isnot(None))
        .distinct()
        .order_by(Entrada.local)
        .all()
        if resultado[0]
    ]

    empresas_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.empresa)
        .filter(Entrada.empresa.isnot(None))
        .distinct()
        .order_by(Entrada.empresa)
        .all()
        if resultado[0]
    ]

    funcionarios_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.funcionario)
        .filter(Entrada.funcionario.isnot(None))
        .distinct()
        .order_by(Entrada.funcionario)
        .all()
        if resultado[0]
    ]

    classes_sst_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.class_sst)
        .filter(Entrada.class_sst.isnot(None))
        .distinct()
        .order_by(Entrada.class_sst)
        .all()
        if resultado[0]
    ]

    classes_ambientais_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.class_ambiental)
        .filter(Entrada.class_ambiental.isnot(None))
        .distinct()
        .order_by(Entrada.class_ambiental)
        .all()
        if resultado[0]
    ]

    pareceres_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.parecer)
        .filter(Entrada.parecer.isnot(None))
        .distinct()
        .order_by(Entrada.parecer)
        .all()
        if resultado[0]
    ]

    justificativas_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.obs_justificativa)
        .filter(Entrada.obs_justificativa.isnot(None))
        .distinct()
        .order_by(Entrada.obs_justificativa)
        .all()
        if resultado[0]
    ]

    procedencias_disponiveis = [
        resultado[0]
        for resultado in db.session.query(Entrada.obs_sprocedencia)
        .filter(Entrada.obs_sprocedencia.isnot(None))
        .distinct()
        .order_by(Entrada.obs_sprocedencia)
        .all()
        if resultado[0]
    ]

    condicoes_brutas = (
        db.session.query(Entrada.multipla_condição)
        .filter(Entrada.multipla_condição.isnot(None))
        .all()
    )
    condicoes_disponiveis = sorted(
        {
            item.strip()
            for (valor,) in condicoes_brutas
            if valor
            for item in valor.split(',')
            if item.strip()
        }
    )

    comportamentos_brutos = (
        db.session.query(Entrada.multipla_comportamento)
        .filter(Entrada.multipla_comportamento.isnot(None))
        .all()
    )
    comportamentos_disponiveis = sorted(
        {
            item.strip()
            for (valor,) in comportamentos_brutos
            if valor
            for item in valor.split(',')
            if item.strip()
        }
    )

    ambientais_brutos = (
        db.session.query(Entrada.multipla_ambiental)
        .filter(Entrada.multipla_ambiental.isnot(None))
        .all()
    )
    ambientais_disponiveis = sorted(
        {
            item.strip()
            for (valor,) in ambientais_brutos
            if valor
            for item in valor.split(',')
            if item.strip()
        }
    )

    anos_disponiveis = sorted(
        {
            int(ano)
            for (ano,) in db.session.query(db.func.strftime("%Y", Entrada.data))
            .filter(Entrada.data.isnot(None))
            .distinct()
            .all()
            if ano
        }
    )

    meses_disponiveis = sorted(
        {
            int(mes)
            for (mes,) in db.session.query(db.func.strftime("%m", Entrada.data))
            .filter(Entrada.data.isnot(None))
            .distinct()
            .all()
            if mes
        }
    )

    filtros_ativos = {chave: valor for chave, valor in filtros_selecionados.items() if valor}

    dataset_meta = {
        "total": len(entradas_filtradas),
        "filters": filtros_ativos,
    }

    return render_template(
        'graficos.html',
        chart_classificacao=preparar_dados(contagem_class),
        chart_local=preparar_dados(contagem_local),
        chart_causa=preparar_dados(contagem_agentes),
        chart_condicoes=preparar_dados(contagem_multipla_condição),
        chart_comportamentos=preparar_dados(contagem_multipla_comportamento),
        chart_ambientais=preparar_dados(contagem_multipla_ambiental),
        chart_quase_acidentes=preparar_dados(contagem_class_sst),
        chart_por_dia=preparar_dados(contagem_por_dia),
        filtros=filtros_selecionados,
        emitentes=emitentes_disponiveis,
        causas=causas_disponiveis,
        locais=locais_disponiveis,
        empresas=empresas_disponiveis,
        funcionarios=funcionarios_disponiveis,
        classes_sst=classes_sst_disponiveis,
        classes_ambientais=classes_ambientais_disponiveis,
        pareceres=pareceres_disponiveis,
        justificativas=justificativas_disponiveis,
        procedencias=procedencias_disponiveis,
        condicoes=condicoes_disponiveis,
        comportamentos=comportamentos_disponiveis,
        ambientais=ambientais_disponiveis,
        anos=anos_disponiveis,
        meses=meses_disponiveis,
        dataset_meta=dataset_meta,
    )


if __name__ == "__main__":
    app.run(debug=True)
