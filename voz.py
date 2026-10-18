"""Ouvir: transforma a sua fala em texto com o Whisper (roda no seu PC, grátis).

Usa o faster-whisper no processador. Na primeira vez ele baixa o modelo
(o "small" tem uns 500 MB); depois fica guardado no PC.

Modelos (escolha em Sistema):
- base:   rápido, erra mais em português
- small:  equilíbrio (padrão)
- medium: entende melhor, mas é bem mais lento no processador
"""

import difflib
import io
import os
import re
import threading
import time
import unicodedata
import wave

import banco

TAMANHO_MAXIMO = 15 * 1024 * 1024  # 15 MB: mais que isso não é uma frase falada
MODELOS = ("base", "small", "medium")

_trava = threading.Lock()
_carregado = {"nome": None, "modelo": None}


def _modelo():
    nome = os.getenv("WHISPER_MODELO", "small")
    if nome not in MODELOS:
        nome = "small"
    if _carregado["nome"] != nome:
        from faster_whisper import WhisperModel

        banco.registrar("sistema", f"Carregando o modelo de voz '{nome}' (na primeira vez ele é baixado)")
        _carregado["modelo"] = WhisperModel(nome, device="cpu", compute_type="int8")
        _carregado["nome"] = nome
    return _carregado["modelo"]


TAXA_WHISPER = 16000  # o Whisper trabalha com 16 mil amostras por segundo


def eh_wav(audio):
    return len(audio) > 44 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"


def ler_wav(audio):
    """Lê um WAV (o navegador já manda assim) e devolve o som pronto para o Whisper.
    Usa só o módulo 'wave' do Python: não depende do PyAV, que mudou e quebrou o
    leitor de áudio do faster-whisper (erro 'metadata_errors')."""
    import numpy as np

    with wave.open(io.BytesIO(audio)) as arquivo:
        canais = arquivo.getnchannels()
        largura = arquivo.getsampwidth()
        taxa = arquivo.getframerate()
        bruto = arquivo.readframes(arquivo.getnframes())
    if largura != 2:
        raise ValueError(f"WAV com {largura * 8} bits; esperado 16 bits")
    som = np.frombuffer(bruto, dtype="<i2").astype(np.float32) / 32768.0
    if canais > 1:
        som = som.reshape(-1, canais).mean(axis=1)
    if taxa != TAXA_WHISPER and len(som):
        duracao = len(som) / taxa
        novos = np.linspace(0, duracao, int(duracao * TAXA_WHISPER), endpoint=False)
        som = np.interp(novos, np.arange(len(som)) / taxa, som).astype(np.float32)
    return som


# ---------- Chamar pelo nome ----------

# Palavras que podem vir antes do nome: "ei Jarvis", "hey Jarvis", "ô Jarvis"...
_SAUDACOES = {"ei", "hey", "hei", "ey", "oi", "ola", "o", "e", "fala", "alo", "ai"}
# Jeitos que o Whisper às vezes escreve "Jarvis" em português
_NOMES = {"jarvis", "jarvi", "jarves", "jervis", "javis", "jarbas", "jarbis", "jarvas", "djarvis"}


def _normalizar(palavra):
    sem_acento = unicodedata.normalize("NFD", palavra.lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", sem_acento)


def _parece_jarvis(palavra):
    p = _normalizar(palavra)
    return p in _NOMES or (len(p) >= 5 and difflib.SequenceMatcher(None, p, "jarvis").ratio() >= 0.8)


def detectar_chamado(texto):
    """A frase começa chamando o Jarvis? Devolve (chamou, comando).
    'Jarvis, que horas são?' -> (True, 'que horas são?')
    'Ei Jarvis.'             -> (True, '')   (chamou, mas não disse o quê)
    'o jarvis é legal'       -> (False, '')  (o nome não está no começo)"""
    palavras = (texto or "").split()
    for i, palavra in enumerate(palavras[:3]):
        if _parece_jarvis(palavra):
            resto = " ".join(palavras[i + 1:]).strip()
            return True, resto.lstrip(",.!?;: ").strip()
        if _normalizar(palavra) not in _SAUDACOES:
            break
    return False, ""


def transcrever(audio, registrar_fala=True):
    """Recebe o áudio gravado pela página. Devolve {"texto": ..., "erro": ...}.
    registrar_fala=False (modo escuta): o que foi ouvido não vai para o Registro."""
    if not audio:
        return {"texto": "", "erro": None}
    if len(audio) > TAMANHO_MAXIMO:
        return {"texto": "", "erro": "A gravação ficou grande demais. Fale uma frase de cada vez."}
    try:
        with _trava:  # um áudio por vez: o processador é um só
            modelo = _modelo()
            inicio = time.time()
            entrada = ler_wav(audio) if eh_wav(audio) else io.BytesIO(audio)
            trechos, _info = modelo.transcribe(
                entrada,
                language="pt",
                beam_size=1,  # mais rápido; para frases curtas a precisão quase não muda
                vad_filter=True,  # ignora os silêncios
                initial_prompt="Conversa em português com o assistente Jarvis.",
            )
            texto = " ".join(t.text.strip() for t in trechos).strip()
            duracao = time.time() - inicio
    except ImportError:
        return {"texto": "", "erro": "Falta instalar a voz. No terminal (com o .venv ativo): pip install -r requirements.txt"}
    except Exception as erro:
        banco.registrar("erro", f"Transcrição falhou: {erro}")
        return {"texto": "", "erro": f"Não consegui entender o áudio ({type(erro).__name__})."}
    if registrar_fala:
        banco.registrar("voz", f"Ouvi: {texto}" if texto else "Ouvi só silêncio")
        banco.registrar("tempo", f"Ouvido: transcrição em {duracao:.1f} s")
    return {"texto": texto, "erro": None, "segundos": round(duracao, 1)}


def escutar(audio):
    """Modo escuta: só devolve o que foi dito se a frase começar com 'Jarvis'.
    O resto é descartado e não fica registrado em lugar nenhum."""
    resultado = transcrever(audio, registrar_fala=False)
    if resultado["erro"]:
        return {"chamou": False, "comando": "", "erro": resultado["erro"]}
    chamou, comando = detectar_chamado(resultado["texto"])
    if chamou:
        banco.registrar("voz", f"Chamado pelo nome: {comando or '(só o nome)'}")
        banco.registrar("tempo", f"Ouvido (escuta): transcrição em {resultado['segundos']:.1f} s")
    return {"chamou": chamou, "comando": comando, "erro": None}
