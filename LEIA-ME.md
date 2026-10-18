# Jarvis · Fase 1 (chat no terminal)

## 1. Instalar os programas (uma vez só)

- **Python 3.12**: python.org. Na instalação, marque **"Add Python to PATH"**.
- **Git** e **VS Code** (opcionais agora, úteis depois).
- **Ollama**: ollama.com (o cérebro grátis).

## 2. Baixar o modelo do Ollama

Abra o terminal (PowerShell) e rode:

```
ollama pull qwen2.5:7b
```

São uns 4–5 GB. O qwen2.5 é bom em usar ferramentas e entende português.

## 3. Preparar a pasta

Coloque esta pasta `jarvis` onde quiser (ex.: Documentos). Abra o PowerShell dentro dela e rode:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Se o `activate` der erro de permissão, rode antes:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 4. Criar o .env

Copie o arquivo `.env.exemplo` e renomeie a cópia para `.env`.
Do jeito que está, ele já usa o Ollama.

## 5. Rodar

```
python jarvis.py
```

Teste:
- "que horas são?"
- "vai chover amanhã?"
- "como está o tempo no Rio de Janeiro?"

Quando ele responder usando as ferramentas (aparece `[usando ver_clima...]`), a Fase 1 está pronta.

## Trocar para a API do Claude

No `.env`: mude `CEREBRO=claude` e cole sua chave em `ANTHROPIC_API_KEY`.
A API é paga à parte do plano Pro. Defina um limite de gasto no console.anthropic.com.

---

# Fase 2 (Agenda, Gmail e PC)

## 1. Atualizar os pacotes

Com o `(.venv)` ativo, dentro da pasta jarvis:

```
pip install -r requirements.txt
```

## 2. Configurar o Google (uma vez só)

1. Entre em **console.cloud.google.com** com o Gmail que o Jarvis vai ler.
2. No topo, crie um projeto chamado **Jarvis**.
3. Menu → **APIs e serviços → Biblioteca**. Ative a **Google Calendar API** e a **Gmail API**.
4. Menu → **Google Auth Platform** (ou "Tela de consentimento OAuth"):
   - Nome do app: Jarvis. Email de suporte: o seu.
   - Público: **Externo**.
   - Em **Público / Usuários de teste**, adicione o seu próprio Gmail.
5. Menu → **Clientes** (ou "Credenciais") → **Criar cliente OAuth** → tipo **App para computador**.
6. Baixe o JSON, coloque na pasta jarvis e renomeie para **credentials.json**.

## 3. Primeiro login

Rode `python jarvis.py` e pergunte "o que tenho na agenda hoje?".
O navegador abre pedindo para autorizar. Vai aparecer "O Google não verificou este app":
clique em **Avançado → Acessar Jarvis**. É normal, o app é seu.
O Jarvis só pede permissão de **leitura**: não envia nem apaga nada.

## 4. Testar

- "o que tenho na agenda esta semana?"
- "tenho email não lido?"
- "abre o bloco de notas"
- "acha meus arquivos com 'jarvis' no nome"

## Programas permitidos

O Jarvis só abre o que está no `programas.json`. Para adicionar um programa,
coloque o nome e o caminho do .exe (com barras duplas `\\`), por exemplo:

```
"minecraft": "C:\\XboxGames\\Minecraft Launcher\\Content\\Minecraft.exe"
```

Para achar o caminho: clique com o botão direito no atalho → Abrir local do arquivo.

## Se der erro de login

Em modo de teste, o Google pede login de novo a cada 7 dias. Se der erro de
"token", apague o `token.json` e rode de novo.

---

# Fase 3 (o software do Jarvis)

## 1. Atualizar os pacotes

Com o `(.venv)` ativo, dentro da pasta jarvis:

```
pip install -r requirements.txt
```

## 2. Abrir o software

```
python servidor.py
```

O navegador abre sozinho em http://127.0.0.1:8000. Deixe o terminal aberto:
ele é o "motor". Para desligar, aperte **Ctrl+C** no terminal.

O `python jarvis.py` (chat no terminal) continua funcionando também.

## 3. As telas

| Tela | O que tem |
| --- | --- |
| Conversa | Chat com o orbe. Enter envia, Shift+Enter pula linha |
| Avisos | Lembretes que o Jarvis deixou. O número no menu são os não lidos |
| Armazenamento | O que ele sabe sobre você. Adicione e apague à vontade |
| Configurações | Trocar cérebro, modelo, cidade e chave da API sem abrir o .env |
| Registro | Tudo que ele fez e quando (ótimo para achar erros) |

## 4. Testar

- "lembra que eu gosto de Minecraft" → aparece no Armazenamento
- "me lembra de estudar para a prova de LE" → aparece em Avisos
- "o que você sabe sobre mim?"
- "o que tenho na agenda amanhã?"

## Lembretes com hora

- "me lembra de estudar às 18h", "me lembra amanhã às 7h30", "me lembra daqui a 20 minutos".
- No horário aparece uma notificação do Windows (com o nome "Windows PowerShell")
  e um alerta com som na tela do Jarvis.
- O Jarvis precisa estar aberto (a janela preta) para avisar. Se ele estava fechado
  na hora, o lembrete aparece assim que você abrir.
- Por enquanto, só hoje ou amanhã. Lembretes agendados ficam em Avisos com
  "AGENDADO" e podem ser cancelados.
- Se a notificação do Windows não aparecer, confira se o "Não incomodar" está desligado.

## Voz (Fase 4a)

1. Instale a parte de voz (uma vez só), com o `(.venv)` ativo:
   ```
   pip install -r requirements.txt
   ```
2. Clique no **microfone**, fale e espere: ele para sozinho quando você fica
   1,5 segundo em silêncio (ou clique de novo para parar).
3. O Jarvis responde em voz alta quando a pergunta foi falada.
   Perguntas digitadas continuam só em texto.

- Na **primeira vez**, o modelo de voz é baixado (o "small" tem uns 500 MB).
  Pode demorar alguns minutos; nas próximas é rápido.
- Na primeira vez o navegador pede permissão para o microfone: clique em **Permitir**.
- Em **Sistema** dá para escolher o modelo do ouvido (base, small, medium) e a
  voz das respostas, com um botão para testar.
- A voz das respostas usa as vozes do Windows. Se não aparecer nenhuma em
  português: Configurações do Windows > Hora e idioma > Fala > Adicionar vozes.

## Testes

```
python testes.py
```

Roda todos os testes (sem precisar do Ollama e sem mexer nos seus dados).
No final deve aparecer **OK**.

## Segurança

- O servidor só aceita comandos da própria página do Jarvis. Outros sites abertos
  no seu navegador são bloqueados (aparece "Acesso bloqueado" no Registro).
- Se o Jarvis ler emails, agenda ou arquivos numa conversa e quiser guardar uma
  memória nessa mesma conversa, ela vai para **Avisos** esperando você aprovar.
  Só aprove o que foi você que pediu.
- O painel nunca abre o login do Google sozinho. Quando o acesso vencer
  (a cada 7 dias em modo de teste), aparece "Reconectar Google".

## Onde ficam os dados

Tudo fica no arquivo `dados/jarvis.db`, só no seu PC. Para zerar tudo,
desligue o servidor e apague a pasta `dados`.

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `servidor.py` | O software: abre a interface no navegador |
| `interface/index.html` | As telas do software |
| `banco.py` | O banco de dados (avisos, memória, registro, conversa) |
| `jarvis.py` | O chat no terminal |
| `notificacao.py` | Notificação do Windows dos lembretes |
| `voz.py` | Ouvido do Jarvis: transforma sua fala em texto (Whisper) |
| `testes.py` | Testes automáticos (rode antes de mexer no código) |
| `cerebros.py` | Os dois cérebros (Ollama e Claude) e o loop do agente |
| `ferramentas.py` | As ferramentas: hora, clima, agenda, emails, abrir programas, buscar arquivos |
| `google_auth.py` | Login no Google (só leitura) |
| `programas.json` | Lista de programas que o Jarvis pode abrir |
| `.env` | Suas configurações e chaves (nunca vai para o GitHub) |
| `credentials.json` / `token.json` | Acesso ao Google (nunca compartilhe) |
