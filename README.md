# TikTok LIVE → VRChat OSC Bridge

Conecta eventos de presente da sua LIVE do TikTok (**@vortexjogosuwu**) diretamente
ao VRChat via OSC, sem depender do Interfuse/Twitch.

```
TikTok LIVE --(GiftEvent)--> Python --(config.yaml)--> OSC --> VRChat
```

## Bibliotecas usadas (verificadas na documentação oficial em set/2026)

| Função | Biblioteca | Repositório |
|---|---|---|
| Conexão com TikTok LIVE | `TikTokLive` | https://github.com/isaackogan/TikTokLive |
| Envio de mensagens OSC | `python-osc` | https://github.com/attwad/python-osc |
| Leitura do config.yaml | `PyYAML` | — |
| Interface gráfica | `tkinter` (embutido no Python) | — |

Não é necessário login, senha ou token do TikTok — a `TikTokLive` conecta
apenas usando o `@username` público do canal, lendo o mesmo WebSocket que
qualquer espectador da LIVE recebe.

> ⚠️ `TikTokLive` é um projeto de engenharia reversa (não é uma API oficial
> do TikTok). Ele pode quebrar se o TikTok mudar o protocolo internamente —
> nesse caso, normalmente basta atualizar a lib (`pip install -U TikTokLive`).

## Instalação

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Requer Python 3.10+ (testado com o fluxo pensado para Python 3.12).

A interface gráfica usa `tkinter`, que já vem junto com o Python na
maioria das instalações (Windows e macOS). No Linux, se `python app.py`
reclamar que não encontra o `tkinter`, instale o pacote do sistema:

```bash
sudo apt install python3-tk      # Debian/Ubuntu
sudo dnf install python3-tkinter # Fedora
```

## Uso — Interface gráfica (recomendado)

```bash
python app.py
```

Abre uma janela com:

- **Campos no topo**: canal do TikTok, host/porta OSC do VRChat, botões
  "Conectar na LIVE" / "Desconectar", e um indicador de status
  (Desconectado / Conectando / Conectado).
- **Lista de presentes**: mostra todo presente configurado, com o
  endereço OSC, tipo e valor de cada alvo.
  - **Novo presente** / **Editar presente** / **Remover presente**.
  - **Testar selecionado(s)**: dispara o(s) comando(s) OSC da linha
    selecionada na hora — sem precisar mandar presente nenhum no TikTok.
  - Ao criar ou editar um presente, cada alvo também tem seu próprio
    botão **"Testar alvo"** dentro do formulário, então dá pra validar
    se o parâmetro está certo *antes mesmo* de salvar.
  - **Salvar configuração** grava tudo de volta no `config.yaml`
    (⚠️ isso reescreve o arquivo inteiro — comentários do YAML original
    são perdidos nesse processo; os valores continuam intactos).
- **Log**: mesma informação que apareceria no console (`[TIKTOK]`,
  `[OSC]`, `[ERROR]`), só que dentro da janela.

Fluxo recomendado para configurar um presente novo: clique em
**Novo presente** → preencha nome, parâmetro/endereço, tipo e valor →
clique em **Testar alvo** (com o VRChat aberto e OSC habilitado) →
se o avatar reagir do jeito certo, clique em **Salvar presente** e depois
em **Salvar configuração**.

## Uso — Linha de comando (opcional, para quem preferir)

O `main.py` original continua funcionando exatamente igual, sem janela,
para quem quiser rodar em modo terminal/serviço:

```bash
python main.py
```

Saída esperada:

```
[12:00:01] [TIKTOK] Conectando à LIVE de @vortexjogosuwu...
[12:00:02] [TIKTOK] Conectado à LIVE de @vortexjogosuwu
[12:00:15] [TIKTOK] VortexFan enviou Rose x1
[12:00:15] [TIKTOK] Aplicando regra do presente 'Rose' (recebido de VortexFan, quantidade 1)
[12:00:15] [OSC] /avatar/parameters/Outfit = 1
```

## Configuração

Edite `config.yaml`:

```yaml
tiktok:
  username: "vortexjogosuwu"

vrchat:
  osc_host: "127.0.0.1"
  osc_port: 9000

gifts:
  Rose:
    parameter: "Outfit"
    type: int
    value: 1
  Heart:
    parameter: "Outfit"
    type: int
    value: 2
  Galaxy:
    parameter: "Outfit"
    type: int
    value: 3
```

- O **nome do presente** (`Rose`, `Heart`, `Galaxy`, ...) deve ser exatamente
  o nome em inglês que o TikTok usa internamente para aquele presente.
- Cada alvo tem **3 campos livres**: `parameter` (ou `address`), `type` e
  `value` — dá para configurar qualquer combinação, já que cada avatar
  usa parâmetros diferentes:
  - `type: int` → valores inteiros (`0`, `1`, `2`, ...)
  - `type: float` → valores decimais (`0.0` a `1.0`, por exemplo)
  - `type: bool` → `true`/`false`
  - `type: string` → texto livre (**atenção**: o VRChat *não* tem
    parâmetro de avatar do tipo texto — só Int/Float/Bool. `string`
    existe aqui só para o caso de você rotear o mesmo bridge para
    outro programa OSC que aceite texto. Usar `string` num parâmetro
    de avatar gera um aviso no console e provavelmente é ignorado
    pelo VRChat.)
- Por padrão, `parameter: "Outfit"` vira o endereço
  `/avatar/parameters/Outfit`. Se quiser mandar para **qualquer outro
  endereço OSC** (não só parâmetros de avatar), use `address:` no lugar
  de `parameter:` com o caminho completo, ex:
  `address: "/avatar/parameters/MeuParametro"`.
- Um presente pode disparar **mais de um alvo** de uma vez usando a
  forma `parameters:` (lista) em vez de `parameter:`/`type:`/`value:` —
  veja o exemplo `TikTok:` no `config.yaml` (troca a roupa **e** liga um
  efeito ao mesmo tempo).
- No VRChat, cada parâmetro precisa existir no **Animator Controller** do
  seu avatar como um parâmetro Int/Float/Bool sincronizado, e o VRChat
  precisa estar com **OSC habilitado** (Action Menu → Options → OSC → Enabled).

## Uso

Com a LIVE já no ar e o VRChat aberto com OSC habilitado (pela GUI, clique
em "Conectar na LIVE"; pela linha de comando, rode `python main.py`).

Se algum presente estiver configurado com `type: string` apontando para um
parâmetro de avatar, você verá um aviso assim ao iniciar o programa:

```
[12:00:00] [ERROR] [CONFIG] Presente 'Foo': o parâmetro '/avatar/parameters/SomeParam'
está configurado como 'string', mas o VRChat só reconhece parâmetros de avatar
Int/Float/Bool...
```

Isso não impede o programa de rodar — é só um aviso para você trocar o `type`
antes de ligar para o VRChat, já que aquele valor específico não vai fazer
nada no Animator.

Em caso de queda de conexão, o programa tenta reconectar automaticamente
com backoff exponencial (configurável em `reconnect:` no `config.yaml`),
em vez de encerrar.

## Estrutura do projeto

```
tiktok-vrchat/
├── app.py                  # Ponto de entrada da GUI (recomendado)
├── main.py                 # Ponto de entrada em linha de comando
├── config.yaml              # Presentes -> parâmetros OSC + config do VRChat
├── requirements.txt
├── utils_log.py             # Logging padronizado [TIKTOK]/[OSC]/[ERROR]
├── config/
│   └── loader.py              # Carrega, valida e salva config.yaml
├── gui/
│   ├── app.py                 # Janela principal (Tkinter)
│   └── dialogs.py              # Diálogos de criar/editar presente + botão "Testar"
├── tiktok/
│   └── listener.py            # Conexão TikTok LIVE + reconexão + streaks
├── vrchat/
│   └── osc.py                  # Cliente OSC para o VRChat
└── handlers/
    └── gifts.py                 # Presente -> ação OSC (via config.yaml)
```

Isso adiciona pastas `config/` e `gui/` além da estrutura original pedida,
para isolar a leitura/validação do YAML e a interface gráfica do resto do
código — nada no fluxo principal muda por causa disso.

## Combos / streaks

Presentes "streakable" (como a Rose) disparam múltiplos `GiftEvent`
enquanto o combo está em andamento, incrementando `repeat_count`. O
listener só repassa a ação para o handler quando o combo **termina**
(`event.streaking == False`), usando o `repeat_count` final como
quantidade — assim um combo de Rose x20 dispara a troca de roupa **uma
única vez**, não vinte.

## Próximos passos possíveis (não incluídos por padrão)

- Um pequeno mapeamento de "usuário VIP" para pular presentes específicos.
- Persistir logs em arquivo além do console.
- Emitir também eventos por outros gatilhos do TikTok (curtidas, seguidores).

## Sobre suas cores/estilo

As cores (vermelho, laranja, amarelo, com preto e branco) e o padrão visual
do avatar (Vórtex UwU) não têm relação direta com este bridge — a única
coisa que o Python controla aqui é *qual valor numérico* é enviado ao
parâmetro `Outfit` (ou outro parâmetro escolhido). A montagem visual de
cada "roupa" (outfit 1, 2, 3...) dentro dessas cores continua sendo feita
no Unity/VRChat, no Animator Controller do avatar.
