"""Banco de dados do Jarvis (SQLite: um arquivo só, em dados/jarvis.db).

Guarda quatro coisas:
- avisos: mensagens que o Jarvis deixa para você (tela Avisos)
- memoria: o que ele sabe sobre você (tela Armazenamento)
- registro: tudo que ele fez e quando (tela Registro)
- conversa: o histórico do chat (tela Conversa)
"""

import os
import sqlite3
import threading
from datetime import datetime

# JARVIS_DADOS permite os testes usarem uma pasta separada, sem mexer nos seus dados reais
PASTA = os.getenv("JARVIS_DADOS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
CAMINHO = os.path.join(PASTA, "jarvis.db")
_trava = threading.Lock()


def _abrir():
    os.makedirs(PASTA, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO)
    conexao.row_factory = sqlite3.Row
    return conexao


def _executar(sql, parametros=()):
    with _trava:
        conexao = _abrir()
        try:
            cursor = conexao.execute(sql, parametros)
            conexao.commit()
            return cursor.lastrowid
        finally:
            conexao.close()


def _listar(sql, parametros=()):
    with _trava:
        conexao = _abrir()
        try:
            return [dict(linha) for linha in conexao.execute(sql, parametros)]
        finally:
            conexao.close()


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def iniciar():
    for sql in (
        """CREATE TABLE IF NOT EXISTS avisos (
            id INTEGER PRIMARY KEY, criado_em TEXT, tipo TEXT,
            titulo TEXT, texto TEXT, lido INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS memoria (
            id INTEGER PRIMARY KEY, criado_em TEXT, texto TEXT)""",
        """CREATE TABLE IF NOT EXISTS registro (
            id INTEGER PRIMARY KEY, criado_em TEXT, tipo TEXT, detalhe TEXT)""",
        """CREATE TABLE IF NOT EXISTS conversa (
            id INTEGER PRIMARY KEY, criado_em TEXT, papel TEXT, texto TEXT)""",
    ):
        _executar(sql)
    # colunas novas (lembretes com hora): adiciona em bancos antigos sem apagar nada
    colunas = [c["name"] for c in _listar("PRAGMA table_info(avisos)")]
    if "para_quando" not in colunas:
        _executar("ALTER TABLE avisos ADD COLUMN para_quando TEXT")
    if "entregue" not in colunas:
        _executar("ALTER TABLE avisos ADD COLUMN entregue INTEGER DEFAULT 1")


# ---------- Avisos ----------

def criar_aviso(titulo, texto, tipo="info", para_quando=None):
    """para_quando = "AAAA-MM-DD HH:MM": o aviso só aparece como novo nesse horário."""
    novo = _executar(
        "INSERT INTO avisos (criado_em, tipo, titulo, texto, para_quando, entregue) VALUES (?, ?, ?, ?, ?, ?)",
        (agora(), tipo, titulo, texto, para_quando, 0 if para_quando else 1),
    )
    registrar("aviso", f"Lembrete agendado para {para_quando}: {titulo}" if para_quando else f"Novo aviso: {titulo}")
    return novo


def avisos():
    return _listar(
        "SELECT * FROM avisos ORDER BY lido ASC, entregue DESC, "
        "COALESCE(para_quando, criado_em) DESC, id DESC LIMIT 200"
    )


def lembretes_vencidos():
    return _listar(
        "SELECT * FROM avisos WHERE entregue = 0 AND para_quando <= ? ORDER BY para_quando",
        (agora(),),
    )


def marcar_entregue(aviso_id):
    _executar("UPDATE avisos SET entregue = 1 WHERE id = ?", (aviso_id,))


def aviso(aviso_id):
    linhas = _listar("SELECT * FROM avisos WHERE id = ?", (aviso_id,))
    return linhas[0] if linhas else None


def contar_nao_lidos():
    return _listar("SELECT COUNT(*) AS n FROM avisos WHERE lido = 0 AND entregue = 1")[0]["n"]


def marcar_lido(aviso_id):
    _executar("UPDATE avisos SET lido = 1 WHERE id = ?", (aviso_id,))


def apagar_aviso(aviso_id):
    _executar("DELETE FROM avisos WHERE id = ?", (aviso_id,))


# ---------- Memória ----------

def lembrar(texto):
    novo = _executar("INSERT INTO memoria (criado_em, texto) VALUES (?, ?)", (agora(), texto))
    registrar("memoria", f"Guardou: {texto}")
    return novo


def memorias():
    return _listar("SELECT * FROM memoria ORDER BY id ASC")


def apagar_memoria(memoria_id):
    _executar("DELETE FROM memoria WHERE id = ?", (memoria_id,))
    registrar("memoria", f"Apagou a memória {memoria_id}")


# ---------- Registro ----------

def registrar(tipo, detalhe):
    _executar(
        "INSERT INTO registro (criado_em, tipo, detalhe) VALUES (?, ?, ?)",
        (agora(), tipo, str(detalhe)[:500]),
    )


def registro(limite=300):
    return _listar("SELECT * FROM registro ORDER BY id DESC LIMIT ?", (limite,))


def limpar_registro_antigo(manter=2000):
    _executar(
        "DELETE FROM registro WHERE id NOT IN (SELECT id FROM registro ORDER BY id DESC LIMIT ?)",
        (manter,),
    )


# ---------- Conversa ----------

def salvar_mensagem(papel, texto):
    _executar(
        "INSERT INTO conversa (criado_em, papel, texto) VALUES (?, ?, ?)",
        (agora(), papel, texto),
    )


def conversa(limite=100):
    linhas = _listar("SELECT * FROM conversa ORDER BY id DESC LIMIT ?", (limite,))
    return list(reversed(linhas))


def limpar_conversa():
    _executar("DELETE FROM conversa")
    registrar("sistema", "Nova conversa iniciada")


iniciar()
limpar_registro_antigo()
