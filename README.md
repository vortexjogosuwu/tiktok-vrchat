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
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
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

## Uso — Windows (mais fácil: arquivos .bat)

Dois atalhos prontos, que criam e usam automaticamente um ambiente
virtual Python local (pasta `.venv`, isolado do resto do seu sistema) e
garantem as dependências do `requirements.txt` **em toda execução**
(o `pip` pula rapidamente o que já está instalado, então isso não deixa
o início mais lento, e evita erros do tipo "ModuleNotFoundError" se o
ambiente ficar incompleto por qualquer motivo):

- **`iniciar_app.bat`** → abre a interface gráfica (equivalente a `python app.py`).
- **`iniciar_main.bat`** → roda a versão em linha de comando (equivalente a `python main.py`).

Basta dar dois cliques no `.bat` desejado. Na primeira execução, a criação
do ambiente virtual e a instalação das dependências podem demorar um
pouco — nas próximas vezes é praticamente instantâneo.

> Se você já tinha uma pasta `venv` (sem o ponto) de uma versão anterior
> deste projeto, pode apagá-la — a pasta usada agora é `.venv`.

> Se mesmo assim algo parecer quebrado, apague a pasta `.venv` inteira e
> rode o `.bat` de novo para recriar do zero.

Isso exige que o Python já esteja instalado no Windows (com a opção
"Add Python to PATH" marcada durante a instalação) — os `.bat` avisam
se o Python não for encontrado.

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
    selecionada **na hora**, sem duração nem revert — ideal pra
    conferir rapidamente se um endereço/valor está certo.
  - **Testar presente (completo)**: roda o presente **inteiro**, exatamente
    como aconteceria numa LIVE de verdade — aplica os alvos, espera a
    duração (se o presente tiver uma) e reverte automaticamente ao
    final. Funciona **com ou sem estar conectado ao TikTok** — não
    precisa abrir uma LIVE pra testar se a fila e o revert estão
    funcionando.
  - **Voltar para roupa padrão**: troca pra roupa padrão (`vrchat.default_revert`/
    `default_revert_outfit`) imediatamente, sem mexer em nada que esteja
    na fila. Útil pra "resetar" o avatar manualmente a qualquer momento.
  - **🚨 PÂNICO**: pede confirmação e, se você confirmar, cancela **tudo**
    que estiver ativo ou esperando na fila de presentes com duração (sem
    deixar nenhum deles rodar o próprio revert) e troca pra roupa padrão
    na hora. Serve como um botão de emergência caso algo saia do
    controle durante uma LIVE.
  - Ao criar ou editar um presente, cada alvo também tem seu próprio
    botão **"Testar"** dentro do formulário, então dá pra validar
    se o parâmetro está certo *antes mesmo* de salvar.
  - **Salvar configuração** grava tudo de volta no `config.yaml`
    (⚠️ isso reescreve o arquivo inteiro — comentários do YAML original
    são perdidos nesse processo; os valores continuam intactos). Se você
    já estiver conectado à LIVE quando salvar, a conexão atual continua
    usando a configuração antiga até você desconectar e conectar de novo
    — mas o botão "Testar presente" já usa a versão nova na hora.
- **Log**: mesma informação que apareceria no console (`[TIKTOK]`,
  `[OSC]`, `[ERROR]`), só que dentro da janela.

Fluxo recomendado para configurar um presente novo: clique em
**Novo presente** → preencha nome, parâmetro/endereço, tipo e valor
(use "Escolher da lista..." e "Parâmetros do avatar..." pra não
precisar adivinhar nomes) → clique em **Testar** no alvo pra conferir
no VRChat → salve o presente → selecione ele na lista principal e
clique em **Testar presente (completo)** pra conferir o ciclo inteiro
(inclusive duração/revert, se configurados) — tudo isso sem precisar
estar numa LIVE. Só depois de conferir que está tudo certo, clique em
**Salvar configuração**.

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

O `config.yaml` já vem **enxuto**, só com o essencial pra você montar do
zero: seu canal, host/porta do VRChat, e um conjunto `Padrao` (que você
edita com os parâmetros reais do seu avatar). Não tem nenhum presente de
exemplo — adicione os seus pela GUI (botão "Novo presente") ou editando
o arquivo direto. Os trechos abaixo são só pra ilustrar o formato.

Edite `config.yaml` (ou use a GUI, que edita esse arquivo pra você):

```yaml
tiktok:
  username: "vortexjogosuwu"
```

> `vortexjogosuwu` é só o valor **padrão de exemplo** (o canal de quem
> pediu esse projeto) — não tem nada fixo no código apontando pra esse
> canal especificamente. Se você (ou qualquer outra pessoa) for usar
> este programa no seu próprio canal, troque esse valor pelo seu `@`,
> tanto no `config.yaml` quanto no campo "Canal TikTok (@)" da GUI.

```yaml
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

### Pausa automática entre alvos (parâmetros "gatilho")

Quando um presente ou conjunto tem **mais de um alvo** (ex: liga um
parâmetro e depois desliga, como um `OUTFIT = 1` seguido de `OUTFIT = 0`
pra disparar uma transição no Animator), o programa manda cada um em
**sequência**, com uma pequena pausa automática entre eles (não dá pra
configurar isso em segundos de propósito — é só uma folga de segurança
fixa). Isso existe porque, se os dois valores forem mandados juntos
demais, o VRChat pode nunca chegar a "ver" o valor intermediário —
comum em avatares que usam um parâmetro Int como gatilho de animação.

Isso vale pra qualquer lista de alvos: presentes com `parameters:`,
conjuntos de roupa, e o revert (próprio ou padrão global). Não muda
nada pra alvos únicos.

### Conjuntos de roupa (outfits) — troca por peça

Como o seu avatar troca de roupa **por peça** (calcinha, sutiã, camisa,
calça/saia, acessórios...) em vez de um "look" inteiro de uma vez, dá
para definir **conjuntos reutilizáveis** — uma lista de peças — e
referenciar esse conjunto em vários presentes, em vez de repetir a
lista toda vez:

```yaml
outfits:
  Padrao:
    - parameter: "Calcinha"
      type: bool
      value: false
    - parameter: "Sutia"
      type: bool
      value: false
    - parameter: "Camisa"
      type: int
      value: 0

  Biquini:
    - parameter: "Calcinha"
      type: bool
      value: true
    - parameter: "Sutia"
      type: bool
      value: true
    - parameter: "Camisa"
      type: int
      value: 0

gifts:
  Heart:
    outfit: "Biquini"     # veste as 3 peças do conjunto de uma vez
    duration_minutes: 10   # fica 10 min, depois volta pro padrão
```

Um presente pode combinar um conjunto **com alvos extras** ao mesmo
tempo (ex: veste o "Biquini" e ainda liga um efeito Bool separado) —
veja o exemplo `Diamond:` no `config.yaml`. E o `revert` também aceita
um conjunto (`revert_outfit: "Padrao"`) em vez de listar peça por peça.

Na GUI, o botão **"Conjuntos de roupa"** abre um gerenciador (criar,
editar, remover conjuntos, com botão de testar cada peça), e o
formulário de presente tem um menu suspenso pra escolher um conjunto
pronto.

### Duração e fila (roupa temporária exclusiva)

Um presente pode ter uma **duração**, usando `duration_minutes` (ou
`duration_seconds`, se preferir mais precisão):

```yaml
gifts:
  Heart:
    parameter: "Outfit"
    type: int
    value: 5
    duration_minutes: 10
```

Como funciona:

- Ao receber `Heart`, o avatar troca para `Outfit = 5` e fica assim por
  **10 minutos**.
- Se **outro** presente com duração chegar enquanto o `Heart` ainda está
  ativo, ele **não sobrepõe** — entra numa fila (FIFO) e espera.
- Quando os 10 minutos acabam, o programa manda automaticamente os
  valores de **"revert"** (a roupa padrão) e só depois libera o próximo
  da fila, se houver.
- Se a fila estiver vazia quando termina, o avatar simplesmente fica na
  roupa padrão até o próximo presente com duração chegar.
- Presentes **sem** duração (como `Galaxy` ou `Lion` no exemplo) não
  entram nessa fila — continuam disparando na hora, em paralelo, como
  sempre.

Para onde reverter, você tem duas opções (cada uma aceita um conjunto
pré-criado OU uma lista manual de alvos):

1. **Padrão global** — usado por qualquer presente com duração que não
   define seu próprio revert:
   ```yaml
   vrchat:
     default_revert_outfit: "Padrao"   # usa um conjunto de 'outfits:'
     # OU, sem conjunto, uma lista manual:
     # default_revert:
     #   - parameter: "Outfit"
     #     type: int
     #     value: 0
   ```
2. **Revert próprio do presente**, com `revert_outfit:` (nome de um
   conjunto) e/ou `revert:` (lista manual, mesmo formato de
   `parameters:`) — útil se, por exemplo, um presente também ligou um
   efeito Bool que precisa ser desligado ao reverter (veja o exemplo
   `Diamond:` no `config.yaml`):
   ```yaml
   gifts:
     Diamond:
       outfit: "Biquini"
       parameters:
         - parameter: "GlowEffect"
           type: bool
           value: true
       duration_minutes: 30
       revert_outfit: "Padrao"
       revert:
         - parameter: "GlowEffect"
           type: bool
           value: false
   ```

Se um presente tiver duração e **nenhum dos dois** (nem revert próprio
nem o padrão global), o programa recusa carregar o `config.yaml` e
explica exatamente o que falta — assim nunca fica um presente "preso"
sem saber para onde voltar.

Na GUI, tudo isso é configurável com o mouse: o formulário de presente
tem um menu suspenso pra escolher o conjunto a vestir, uma caixinha
"Este presente fica ativo por um tempo..." + campo de minutos + um menu
suspenso pra escolher o conjunto de revert, e o botão **"Roupa padrão
(revert global)"** na janela principal edita o padrão global.

### Lista de nomes de presente (sem precisar adivinhar)

No formulário de presente, o campo "Nome do presente" tem um botão
**"Escolher da lista..."** ao lado, que abre duas fontes de nomes:

1. **"Buscar da LIVE agora"** — a fonte confiável: busca o catálogo
   real de presentes direto do TikTok, do seu canal. Só funciona
   **enquanto você está ao vivo no momento da busca** (é assim que o
   TikTok disponibiliza essa lista — não tem como consultar fora de
   uma transmissão ativa). Mostra nome e valor em diamantes de cada
   presente disponível no seu canal.
2. **Sugestões comuns** — uma lista offline de nomes populares
   (Rose, TikTok, GG, Galaxy, Lion, Money Gun, etc.), disponível a
   qualquer momento, para quando você não está ao vivo. **Não é uma
   lista oficial** e pode variar por conta/região/ficar desatualizada
   — é só um ponto de partida para não digitar errado.

Tem um campo de filtro para buscar por nome, e duplo-clique (ou o
botão "Usar este nome") preenche o campo do presente automaticamente.

> Dica: o jeito mais garantido de saber os nomes certos é ficar de
> olho no **Log** da GUI durante uma LIVE de verdade — toda vez que
> alguém manda um presente, o nome exato aparece ali
> (`[TIKTOK] Fulano enviou X x1`), mesmo que ainda não esteja
> configurado.

### Lista de parâmetros do avatar (sem precisar adivinhar nomes)

Na GUI, o botão **"Parâmetros do avatar..."** lê os arquivos que o
**próprio VRChat** já grava no seu computador com todo parâmetro do
Animator do avatar que você carregou (nome, endereço OSC e tipo
Int/Float/Bool), então você não precisa adivinhar nomes de parâmetro.

Como funciona:

1. No VRChat, carregue o avatar com **OSC habilitado** (Action Menu →
   OSC → Enabled) pelo menos uma vez. Isso faz o VRChat gerar um
   arquivo em:
   `%USERPROFILE%\AppData\LocalLow\VRChat\VRChat\OSC\{seu user id}\Avatars\{avatar id}.json`
2. Clique em **"Parâmetros do avatar..."** na GUI. Ela lê esse arquivo
   e mostra uma tabela com **todos** os parâmetros: nome, endereço OSC,
   tipo, e se dá pra "setar" ele de fora (alguns parâmetros são só de
   leitura — ex: velocidade — e não servem pra trocar roupa).
3. Selecione uma linha e use **"Copiar nome"** / **"Copiar endereço"**
   para colar depois num alvo, ou **"Usar este parâmetro..."** para
   abrir um alvo já pré-preenchido, pronto pra você só definir o valor
   e testar.

> Essa leitura só funciona no Windows (onde o VRChat roda) e só depois
> que o avatar foi carregado pelo menos uma vez com OSC habilitado. Se
> o VRChat nunca gerou esse arquivo ainda, a tela avisa e você pode
> continuar digitando os parâmetros manualmente normalmente.

> ⚠️ Se você fechar o programa inteiro enquanto um presente com duração
> ainda está ativo, o revert automático daquele presente não roda (o
> processo é encerrado antes do tempo acabar). Clicar em **Desconectar**
> sozinho não tem mais esse problema — a fila continua rodando
> normalmente em segundo plano mesmo desconectado da LIVE, então o
> revert acontece igual.

### Se um presente com duração não voltou pra roupa padrão sozinho

O log (na GUI ou no console) agora mostra, assim que o presente chega,
exatamente o que vai acontecer — incluindo uma linha `Revert (...):
/avatar/parameters/X=valor` com os alvos resolvidos. Se algo estiver
errado, o log aponta a causa:

- **`[TIKTOK] ... é um presente com duração — enviando para a fila.
  Revert (NENHUM configurado): (vazio)`** → o presente não tem revert
  próprio nem roupa padrão global. Configure um dos dois (aba do
  presente ou botão "Roupa padrão (revert global)").
- **`[ERROR] Tempo de 'X' esgotado, mas NÃO havia nenhum alvo de revert
  configurado`** → mesma causa acima, mas avisado no momento em que o
  tempo realmente acabou.
- Se a linha `Revert (...)` mostrar os alvos certos mas o avatar mesmo
  assim não mudou, confira se o parâmetro realmente existe no seu
  avatar (use "Parâmetros do avatar..." para conferir o nome exato) e
  se o valor de revert é do tipo certo (`int`/`float`/`bool`).
- Verifique também a coluna **"Duração"** na lista principal de
  presentes: se estiver mostrando `-` para um presente que deveria ter
  duração, o campo não foi salvo — edite o presente de novo, marque a
  caixinha de duração e salve.

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
├── iniciar_app.bat          # Atalho Windows: cria .venv + roda app.py
├── iniciar_main.bat         # Atalho Windows: cria .venv + roda main.py
├── config.yaml              # Presentes -> parâmetros OSC + config do VRChat
├── requirements.txt
├── utils_log.py             # Logging padronizado [TIKTOK]/[OSC]/[ERROR]
├── config/
│   └── loader.py              # Carrega, valida e salva config.yaml
├── gui/
│   ├── app.py                 # Janela principal (Tkinter)
│   └── dialogs.py              # Diálogos de criar/editar presente + botão "Testar"
├── tiktok/
│   ├── listener.py            # Conexão TikTok LIVE + reconexão + streaks
│   └── catalog.py              # Lista de nomes de presente (LIVE + sugestões)
├── vrchat/
│   ├── osc.py                   # Cliente OSC para o VRChat
│   └── discovery.py              # Lê os parâmetros do avatar gravados pelo VRChat
├── handlers/
│   ├── gifts.py               # Presente -> ação OSC (via config.yaml)
│   └── timed_queue.py          # Fila exclusiva de presentes com duração
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
