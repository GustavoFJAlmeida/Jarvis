"""Jarvis - Fase 1: chat no terminal.

Rode com:  python jarvis.py
Para sair: digite "sair"
"""

from dotenv import load_dotenv

load_dotenv()  # carrega as configurações do arquivo .env

from cerebros import criar_cerebro  # noqa: E402


def main():
    try:
        cerebro = criar_cerebro()
    except Exception as erro:
        print(f"Não consegui ligar o cérebro: {erro}")
        print("Confira o arquivo .env e o LEIA-ME.md.")
        return

    print(f"Jarvis online ({type(cerebro).__name__} · {cerebro.modelo}). Digite 'sair' para encerrar.\n")

    while True:
        try:
            texto = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not texto:
            continue
        if texto.lower() in ("sair", "tchau", "exit"):
            break
        try:
            print(f"Jarvis: {cerebro.conversar(texto)}\n")
        except Exception as erro:
            print(f"Jarvis: deu um erro: {erro}\n")

    print("Jarvis desligando. Até mais!")


if __name__ == "__main__":
    main()
