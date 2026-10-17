"""Login no Google (Agenda e Gmail), só leitura.

Na primeira vez abre o navegador para você autorizar.
Depois guarda o acesso no token.json e não pergunta mais
(em modo de teste, o Google pede login de novo a cada 7 dias).
"""

import os

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_TOKEN = os.path.join(PASTA, "token.json")
ARQUIVO_CREDENCIAIS = os.path.join(PASTA, "credentials.json")

PERMISSOES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_credenciais = None


class PrecisaLogin(Exception):
    """O acesso ao Google venceu e só um login no navegador resolve."""


def credenciais(pode_abrir_navegador=True):
    global _credenciais
    if _credenciais and _credenciais.valid:
        return _credenciais

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    cred = None
    if os.path.exists(ARQUIVO_TOKEN):
        cred = Credentials.from_authorized_user_file(ARQUIVO_TOKEN, PERMISSOES)

    if cred and cred.expired and cred.refresh_token:
        try:
            cred.refresh(Request())
        except Exception:
            cred = None  # acesso venceu: precisa de login de novo

    if not cred or not cred.valid:
        if not pode_abrir_navegador:
            raise PrecisaLogin("O acesso ao Google venceu. Peça algo da agenda no chat para entrar de novo.")
        if not os.path.exists(ARQUIVO_CREDENCIAIS):
            raise RuntimeError("Falta o credentials.json na pasta do Jarvis (veja o LEIA-ME).")
        from google_auth_oauthlib.flow import InstalledAppFlow

        print("  [abrindo o navegador para você autorizar o Google...]")
        fluxo = InstalledAppFlow.from_client_secrets_file(ARQUIVO_CREDENCIAIS, PERMISSOES)
        cred = fluxo.run_local_server(port=0)

    with open(ARQUIVO_TOKEN, "w") as arquivo:
        arquivo.write(cred.to_json())

    _credenciais = cred
    return cred
