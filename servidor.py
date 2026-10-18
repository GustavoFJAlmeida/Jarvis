"""Jarvis - Fase 3: o software.

Rode com:  python servidor.py
Ele abre sozinho no navegador em http://127.0.0.1:8000
Para desligar: Ctrl+C no terminal.
"""

import asyncio
import os
import threading
import time
import webbrowser

from dotenv import load_dotenv, set_key

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ENV = os.path.join(PASTA, ".env")
load_dotenv(ARQUIVO_ENV)

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import banco  # noqa: E402
import ferramentas  # noqa: E402
import notificacao  # noqa: E402
import voz  # noqa: E402
from cerebros import criar_cerebro  # noqa: E402

PORTA = 8000
app = FastAPI(title="Jarvis")
estado = {"cerebro": None, "erro": None}
trava_cerebro = threading.Lock()

# ---------- Segurança: só a própria página do Jarvis pode dar ordens ----------
# Qualquer site aberto no seu navegador também roda no seu PC e poderia tentar
# falar com o Jarvis. Estas listas garantem que só a página do Jarvis seja aceita.
HOSTS_PERMITIDOS = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
ORIGENS_PERMITIDAS = {f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}"}


def _acesso_permitido(cabecalhos):
    if cabecalhos.get("host") not in HOSTS_PERMITIDOS:
        return False
    origem = cabecalhos.get("origin")
    return origem is None or origem in ORIGENS_PERMITIDAS


@app.middleware("http")
async def so_o_proprio_jarvis(request: Request, seguir):
    if not _acesso_permitido(request.headers):
        banco.registrar("erro", f"Acesso bloqueado de {request.headers.get('origin') or request.headers.get('host')}")
        return JSONResponse({"erro": "acesso negado"}, status_code=403)
    return await seguir(request)


def ligar_cerebro():
    try:
        estado["cerebro"] = criar_cerebro(banco.conversa(limite=20))
        estado["erro"] = None
        banco.registrar("sistema", f"Cérebro ligado: {type(estado['cerebro']).__name__} ({estado['cerebro'].modelo})")
    except Exception as erro:
        estado["cerebro"] = None
        estado["erro"] = str(erro)
        banco.registrar("erro", f"Não consegui ligar o cérebro: {erro}")


ligar_cerebro()
if not banco.avisos():
    banco.criar_aviso(
        "Bem-vindo ao software do Jarvis",
        "Aqui aparecem os lembretes e avisos que ele deixar para você. "
        "Experimente pedir: \"me lembra de estudar amanhã\".",
    )


# ---------- Página ----------

@app.get("/")
def pagina():
    return FileResponse(os.path.join(PASTA, "interface", "index.html"))


# ---------- Conversa (tempo real) ----------

# Cada janela do Jarvis aberta tem uma fila de eventos. Tudo que vai para a tela
# (pedaços da resposta, ferramentas, lembretes) passa pela fila, em ordem.
_conexoes = set()
_trava_conexoes = threading.Lock()


def transmitir(evento):
    """Manda um evento para todas as janelas abertas. Pode ser chamado de qualquer thread."""
    with _trava_conexoes:
        destinos = list(_conexoes)
    for fila, loop in destinos:
        try:
            loop.call_soon_threadsafe(fila.put_nowait, evento)
        except RuntimeError:
            pass  # janela fechando


@app.websocket("/ws")
async def conversa_ao_vivo(socket: WebSocket):
    # navegadores sempre mandam a origem no WebSocket: sem ela ou de outro site, recusa
    if not _acesso_permitido(socket.headers) or socket.headers.get("origin") is None:
        banco.registrar("erro", f"Conexão bloqueada de {socket.headers.get('origin')}")
        await socket.close(code=1008)
        return
    await socket.accept()
    loop = asyncio.get_running_loop()
    fila = asyncio.Queue()
    conexao = (fila, loop)
    with _trava_conexoes:
        _conexoes.add(conexao)

    def mandar(evento):  # seguro para chamar de qualquer thread
        loop.call_soon_threadsafe(fila.put_nowait, evento)

    async def remetente():
        try:
            while True:
                await socket.send_json(await fila.get())
        except Exception:
            pass  # janela fechada

    tarefa = asyncio.create_task(remetente())
    try:
        while True:
            dados = await socket.receive_json()
            texto = (dados.get("texto") or "").strip()
            if not texto:
                continue
            if estado["cerebro"] is None:  # ex.: Ollama estava fechado; tenta de novo
                await asyncio.to_thread(ligar_cerebro)
            cerebro = estado["cerebro"]
            if cerebro is None:
                mandar({
                    "tipo": "resposta",
                    "texto": f"Meu cérebro está desligado. {estado['erro']}",
                    "avisos": banco.contar_nao_lidos(),
                })
                continue

            banco.salvar_mensagem("usuario", texto)

            tempos = {"inicio": time.time(), "primeira": None}

            def ao_escrever(parcial):
                if tempos["primeira"] is None:
                    tempos["primeira"] = time.time()
                mandar({"tipo": "parcial", "texto": parcial})

            def pensar():
                with trava_cerebro:
                    return cerebro.conversar(
                        texto,
                        lambda nome: mandar({"tipo": "ferramenta", "nome": nome}),
                        ao_escrever=ao_escrever,
                        ao_descartar=lambda: mandar({"tipo": "descartar"}),
                    )

            try:
                resposta = await asyncio.to_thread(pensar)
                fim = time.time()
                primeira = f"{tempos['primeira'] - tempos['inicio']:.1f} s" if tempos["primeira"] else "-"
                banco.registrar("tempo", f"Cérebro: primeira palavra em {primeira}, resposta completa em {fim - tempos['inicio']:.1f} s")
            except Exception as erro:
                banco.registrar("erro", str(erro))
                resposta = f"Deu um erro: {erro}"

            banco.salvar_mensagem("jarvis", resposta)
            mandar({"tipo": "resposta", "texto": resposta, "avisos": banco.contar_nao_lidos()})
    except WebSocketDisconnect:
        pass
    finally:
        with _trava_conexoes:
            _conexoes.discard(conexao)
        tarefa.cancel()


# ---------- Lembretes com hora ----------

def entregar_lembretes_vencidos():
    """Confere se algum lembrete chegou na hora. Também entrega os atrasados
    (que venceram com o Jarvis desligado) assim que ele liga."""
    entregues = []
    for aviso in banco.lembretes_vencidos():
        banco.marcar_entregue(aviso["id"])
        banco.registrar("aviso", f"Lembrete entregue: {aviso['titulo']}")
        notificacao.notificar(aviso["titulo"], aviso["texto"])
        transmitir({
            "tipo": "lembrete",
            "titulo": aviso["titulo"],
            "texto": aviso["texto"],
            "avisos": banco.contar_nao_lidos(),
        })
        entregues.append(aviso)
    return entregues


def _agendador():
    while True:
        try:
            entregar_lembretes_vencidos()
        except Exception as erro:
            banco.registrar("erro", f"Agendador de lembretes: {erro}")
        time.sleep(15)


@app.get("/api/conversa")
def historico():
    return banco.conversa()


@app.post("/api/conversa/nova")
def nova_conversa():
    banco.limpar_conversa()
    ligar_cerebro()  # cérebro novo = memória de curto prazo zerada
    return {"ok": True}


# ---------- Avisos ----------

@app.get("/api/avisos")
def listar_avisos():
    return {"avisos": banco.avisos(), "nao_lidos": banco.contar_nao_lidos()}


@app.post("/api/avisos/{aviso_id}/lido")
def ler_aviso(aviso_id: int):
    banco.marcar_lido(aviso_id)
    return {"ok": True}


@app.post("/api/avisos/{aviso_id}/aprovar")
def aprovar_memoria(aviso_id: int):
    """Avisos do tipo 'aprovar_memoria': você aprova e a memória é guardada."""
    aviso = banco.aviso(aviso_id)
    if aviso and aviso["tipo"] == "aprovar_memoria":
        banco.lembrar(aviso["texto"])
        banco.apagar_aviso(aviso_id)
    return {"ok": True}


@app.delete("/api/avisos/{aviso_id}")
def remover_aviso(aviso_id: int):
    banco.apagar_aviso(aviso_id)
    return {"ok": True}


# ---------- Armazenamento (memória) ----------

class NovaMemoria(BaseModel):
    texto: str


@app.get("/api/memoria")
def listar_memoria():
    return banco.memorias()


@app.post("/api/memoria")
def adicionar_memoria(item: NovaMemoria):
    if item.texto.strip():
        banco.lembrar(item.texto.strip())
    return {"ok": True}


@app.delete("/api/memoria/{memoria_id}")
def remover_memoria(memoria_id: int):
    banco.apagar_memoria(memoria_id)
    return {"ok": True}


# ---------- Painel (widgets da tela Conversa) ----------

_cache_painel = {"quando": 0.0, "dados": None}
INICIO = time.time()


@app.get("/api/painel")
def painel():
    if not _cache_painel["dados"] or time.time() - _cache_painel["quando"] > 600:
        cidade = os.getenv("CIDADE_PADRAO", "São José dos Campos")
        dados = {"clima": None, "evento": None, "erro_clima": None}
        try:
            dados["clima"] = ferramentas.clima_resumo(cidade)
            if dados["clima"] is None:
                dados["erro_clima"] = f"cidade '{cidade}' não encontrada"
        except Exception as erro:
            dados["erro_clima"] = f"{type(erro).__name__}: {erro}"[:120]
            banco.registrar("erro", f"Painel (clima): {type(erro).__name__}: {erro}")
        try:
            dados["evento"] = ferramentas.proximo_evento()
        except Exception as erro:
            banco.registrar("erro", f"Painel (agenda): {erro}")
        # se o clima falhou, tenta de novo em 1 minuto em vez de 10
        quando = time.time() if dados["clima"] else time.time() - 540
        _cache_painel.update(quando=quando, dados=dados)

    cerebro = estado["cerebro"]
    return {
        **_cache_painel["dados"],
        "avisos": banco.contar_nao_lidos(),
        "memorias": len(banco.memorias()),
        "cerebro": f"{type(cerebro).__name__.replace('Cerebro', '')} · {cerebro.modelo}" if cerebro else "desligado",
        "ligado_ha_min": int((time.time() - INICIO) // 60),
    }


# ---------- Registro ----------

@app.get("/api/registro")
def listar_registro():
    return banco.registro()


# ---------- Configurações ----------

CAMPOS = ["CEREBRO", "OLLAMA_MODELO", "CLAUDE_MODELO", "CIDADE_PADRAO", "WHISPER_MODELO", "ABRIR_JARVIS"]


PADROES = {"CEREBRO": "ollama", "OLLAMA_MODELO": "qwen2.5:7b", "WHISPER_MODELO": "small",
           "CIDADE_PADRAO": "São José dos Campos", "ABRIR_JARVIS": "janela"}


class Configuracoes(BaseModel):
    CEREBRO: str | None = None
    OLLAMA_MODELO: str | None = None
    CLAUDE_MODELO: str | None = None
    CIDADE_PADRAO: str | None = None
    WHISPER_MODELO: str | None = None
    ABRIR_JARVIS: str | None = None
    ANTHROPIC_API_KEY: str | None = None


def _configuracoes_atuais():
    chave = os.getenv("ANTHROPIC_API_KEY", "")
    cerebro = estado["cerebro"]
    return {
        **{campo: os.getenv(campo) or PADROES.get(campo, "") for campo in CAMPOS},
        "tem_chave": bool(chave) and chave != "cole-sua-chave-aqui",  # a chave nunca sai do servidor
        "cerebro_ligado": cerebro is not None,
        "cerebro_nome": f"{type(cerebro).__name__} · {cerebro.modelo}" if cerebro else "",
        "erro": estado["erro"],
    }


@app.post("/api/ouvir")
async def ouvir(request: Request):
    """Recebe a gravação do microfone e devolve o texto falado."""
    audio = await request.body()
    if request.query_params.get("modo") == "escuta":
        return await asyncio.to_thread(voz.escutar, audio)
    return await asyncio.to_thread(voz.transcrever, audio)


@app.get("/api/modelos")
def modelos_instalados():
    """Modelos já baixados no Ollama, para a lista da tela Sistema."""
    try:
        import ollama

        return {"modelos": sorted(m.model for m in ollama.list().models), "erro": None}
    except Exception:
        return {"modelos": [], "erro": "O Ollama não está aberto."}


@app.get("/api/config")
def ver_configuracoes():
    return _configuracoes_atuais()


@app.post("/api/config")
def salvar_configuracoes(novas: Configuracoes):
    if not os.path.exists(ARQUIVO_ENV):
        open(ARQUIVO_ENV, "a", encoding="utf-8").close()
    for campo, valor in novas.model_dump().items():
        if valor is None or not valor.strip():
            continue  # campo vazio = manter o que já está
        set_key(ARQUIVO_ENV, campo, valor.strip())
        os.environ[campo] = valor.strip()
    banco.registrar("sistema", "Configurações alteradas")
    _cache_painel["dados"] = None  # cidade pode ter mudado: recarrega o clima
    with trava_cerebro:
        ligar_cerebro()
    return _configuracoes_atuais()


def caminho_do_edge():
    """Onde está o Microsoft Edge (vem com o Windows). None se não achar."""
    import shutil

    candidatos = [
        shutil.which("msedge"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
    ]
    return next((c for c in candidatos if c and os.path.exists(c)), None)


def abrir_interface(endereco):
    """Abre o Jarvis numa janela própria do Edge (sem abas, com as vozes naturais).
    Em Sistema dá para escolher o navegador padrão no lugar."""
    import subprocess

    if os.getenv("ABRIR_JARVIS", PADROES["ABRIR_JARVIS"]) == "janela":
        edge = caminho_do_edge()
        if edge:
            subprocess.Popen([edge, f"--app={endereco}", "--window-size=1600,900"])
            return "edge"
        banco.registrar("sistema", "Edge não encontrado; abrindo no navegador padrão")
    webbrowser.open(endereco)
    return "padrao"


if __name__ == "__main__":
    import uvicorn

    endereco = "http://127.0.0.1:8000"
    print(f"Jarvis rodando em {endereco} (Ctrl+C para desligar)")
    threading.Thread(target=_agendador, daemon=True).start()
    threading.Timer(1.5, lambda: abrir_interface(endereco)).start()
    # 127.0.0.1 = só o seu PC acessa. Nunca troque por 0.0.0.0 sem saber o que está fazendo.
    uvicorn.run(app, host="127.0.0.1", port=PORTA, log_level="warning")
