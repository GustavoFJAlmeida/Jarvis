"""Notificação do Windows (aquele balão no canto da tela).

Usa o PowerShell que já vem no Windows: não precisa instalar nada.
A notificação aparece com o nome "Windows PowerShell".

Segurança: o título e o texto vão por variáveis de ambiente, nunca dentro do
comando. Assim, um texto com aspas ou "comandos" escondidos (por exemplo,
vindo de um email) não consegue virar um comando do PowerShell.
"""

import base64
import os
import subprocess
import threading

import banco

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast scenario="reminder"><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual><actions><action content="OK" arguments="ok" activationType="foreground"/></actions><audio src="ms-winsoundevent:Notification.Reminder"/></toast>')
$linhas = $xml.GetElementsByTagName('text')
$linhas.Item(0).AppendChild($xml.CreateTextNode($env:JARVIS_TITULO)) | Out-Null
$linhas.Item(1).AppendChild($xml.CreateTextNode($env:JARVIS_TEXTO)) | Out-Null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""


def montar_comando(titulo, texto):
    """Devolve (comando, ambiente). O texto do usuário fica só no ambiente."""
    codificado = base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")
    comando = ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", codificado]
    ambiente = dict(os.environ, JARVIS_TITULO=f"Jarvis: {titulo}"[:120], JARVIS_TEXTO=str(texto)[:300])
    return comando, ambiente


def _mostrar(titulo, texto):
    comando, ambiente = montar_comando(titulo, texto)
    try:
        resultado = subprocess.run(
            comando, env=ambiente, capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.returncode != 0:
            banco.registrar("erro", f"Notificação do Windows falhou: {resultado.stderr.strip()[:300]}")
    except Exception as erro:
        banco.registrar("erro", f"Notificação do Windows falhou: {erro}")


def notificar(titulo, texto):
    """Mostra a notificação sem travar o Jarvis. Fora do Windows, não faz nada."""
    if os.name != "nt":
        return False
    threading.Thread(target=_mostrar, args=(titulo, texto), daemon=True).start()
    return True
