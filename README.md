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

Duas formas de rodar, dependendo se você quer instalar Python ou não:

- **Sem Python instalado** — gere o `.exe` você mesmo, num Windows,
  rodando `build_exe.bat` (veja [`BUILD.md`](BUILD.md)). É a opção mais
  simples pra distribuir pra outras pessoas usarem depois, já que o
  `.exe` final não exige nada instalado na máquina delas.
- **Com Python** — rodando o código-fonte direto (mais fácil de editar
  e depurar):

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

## Uso — Windows (mais fácil: arquivo .bat)

Um atalho pronto, que cria e usa automaticamente um ambiente virtual
Python local (pasta `.venv`, isolado do resto do seu sistema) e garante
as dependências do `requirements.txt` **em toda execução** (o `pip`
pula rapidamente o que já está instalado, então isso não deixa o
início mais lento, e evita erros do tipo "ModuleNotFoundError" se o
ambiente ficar incompleto por qualquer motivo):

- **`iniciar_app.bat`** → abre a interface gráfica (equivalente a `python app.py`).

Basta dar dois cliques nele. Na primeira execução, a criação do
ambiente virtual e a instalação das dependências podem demorar um
pouco — nas próximas vezes é praticamente instantâneo.

> Se você já tinha uma pasta `venv` (sem o ponto) de uma versão anterior
> deste projeto, pode apagá-la — a pasta usada agora é `.venv`.

> Se mesmo assim algo parecer quebrado, apague a pasta `.venv` inteira e
> rode o `.bat` de novo para recriar do zero.

Isso exige que o Python já esteja instalado no Windows (com a opção
"Add Python to PATH" marcada durante a instalação) — os `.bat` avisam
se o Python não for encontrado.

## Uso — Interface gráfica

```bash
python app.py
```

Abre uma janela com:

- **Campos no topo**: canal do TikTok, host/porta OSC do VRChat, botões
  "Conectar na LIVE" / "Desconectar", e um indicador de status
  (Desconectado / Conectando / Conectado).
- **Ações rápidas** (sempre visíveis, qualquer que seja a aba aberta):
  - **Voltar para roupa padrão**: troca pra roupa padrão imediatamente,
    sem mexer em nada que esteja na fila. Útil pra "resetar" o avatar
    manualmente a qualquer momento.
  - **Ver fila...**: abre uma janela mostrando o presente **ativo agora**
    (com o tempo restante aproximado) e os que estão **esperando** na
    fila, com um botão pra atualizar e um pra limpar.
  - **Limpar fila**: cancela a recompensa ativa e todas as pendentes
    (sem reverter pra roupa padrão automaticamente — pra isso, use o
    PÂNICO) e **avisa quantos foram removidos**.
  - **🚨 PÂNICO**: pede confirmação e, se você confirmar, cancela **tudo**
    que estiver ativo ou esperando na fila de recompensas com duração
    (inclusive os que rodam em paralelo com "ignorar a fila" — veja
    abaixo), troca pra roupa padrão na hora, e **avisa quantas
    recompensas foram canceladas** (quantas da fila + quantas em
    paralelo). Serve como um botão de emergência caso algo saia do
    controle durante uma LIVE.
  - **Parâmetros do avatar...**, **Descobrir valores ao vivo...** (veja
    a seção própria abaixo) e **Salvar configuração** (essa última
    grava tudo de volta no `config.yaml` — ⚠️ isso reescreve o arquivo
    inteiro, comentários do YAML original são perdidos nesse processo,
    mas os valores continuam intactos. Se você já estiver conectado à
    LIVE quando salvar, a conexão atual continua usando a configuração
    antiga até desconectar e conectar de novo — os botões de teste já
    usam a versão nova na hora, sem precisar reconectar).
- **Aba "Recompensas"**: a lista mostra **uma recompensa por linha**
  (não importa quantos presentes disparam ela nem quantos
  itens/parâmetros ela mexa — a coluna "Presentes" mostra quais
  presentes reais do TikTok disparam essa recompensa, e a coluna
  "Itens" resume os alvos, tipo `(5) OUTFIT=2, TOP=1, ...`), com
  colunas extras mostrando se está **ativa**, o **conjunto** usado e se
  ela **ignora a fila** (veja as seções acima). Duplo-clique numa linha
  abre pra edição.
  - **Nova recompensa** / **Editar recompensa** / **Remover recompensa**.
  - **Ativar/Desativar**: liga/desliga a recompensa selecionada com um
    clique, sem precisar apagar nada nem abrir o formulário.
  - **Testar (Aplicar)**: aplica **todos os itens** da recompensa
    selecionada agora, só para conferir — não entra na fila, não conta
    duração e não reverte pra roupa padrão depois. Serve só pra
    verificar que todos os itens aplicam certo, sem interferir na fila
    nem no estado normal do sistema.
  - **Testar (Completo)**: roda a recompensa **inteira**, exatamente
    como aconteceria numa LIVE de verdade — aplica os alvos, entra na
    fila se tiver duração (ou roda em paralelo, se tiver
    `ignore_queue`), espera, e reverte automaticamente ao final.
    Funciona **com ou sem estar conectado ao TikTok**.
  - No formulário de **criar/editar** uma recompensa é onde você
    escolhe o(s) presente(s) do TikTok que a disparam (com "Adicionar",
    "Escolher da lista..." e "Remover selecionado" — pode ser mais de
    um presente pra mesma recompensa) e vê cada item individualmente
    (a lista de alvos), com um botão **"Testar"** próprio em cada um,
    pra validar peça por peça antes mesmo de salvar.
- **Aba "Conjuntos de roupa"**: a lista de conjuntos (`outfits:`), com
  uma coluna **"Padrão?"** marcando com ★ qual é a roupa padrão atual.
  - **Novo conjunto** / **Editar conjunto** / **Remover conjunto**
    (remover avisa se o conjunto é a roupa padrão ou é usado por alguma
    recompensa, mas não impede).
  - **Testar conjunto (completo)**: aplica todas as peças do conjunto
    selecionado agora, em sequência.
  - **★ Definir como roupa padrão**: torna o conjunto selecionado a
    roupa padrão global na hora — sem precisar editar o YAML nem abrir
    outra janela.
  - Renomear um conjunto (editando o nome no formulário) atualiza
    sozinho qualquer recompensa ou a roupa padrão global que já
    apontava pro nome antigo.
- **Log**: mesma informação que apareceria no console (`[TIKTOK]`,
  `[OSC]`, `[ERROR]`), sempre visível embaixo das abas.

Fluxo recomendado: primeiro monte seus **conjuntos de roupa** (aba
"Conjuntos de roupa" → "Novo conjunto" → adicione as peças com
"Parâmetros do avatar..." pra não adivinhar nomes → teste cada peça →
defina um deles como padrão com "★ Definir como roupa padrão"). Depois
vá pra aba **"Recompensas"** → "Nova recompensa" → dê um nome livre →
adicione o(s) presente(s) do TikTok que a disparam → escolha um
conjunto pronto e/ou alvos extras → salve → selecione a recompensa e
clique em **Testar (Completo)** pra conferir o ciclo inteiro (inclusive
duração/revert) — tudo isso sem precisar estar numa LIVE. Só depois de
conferir que está tudo certo, clique em
**Salvar configuração**.

## Configuração

O `config.yaml` já vem **enxuto**, só com o essencial pra você montar do
zero: seu canal, host/porta do VRChat, e um conjunto `Padrao` (que você
edita com os parâmetros reais do seu avatar). Não tem nenhuma recompensa
de exemplo — adicione as suas pela GUI (botão "Nova recompensa") ou
editando o arquivo direto. Os trechos abaixo são só pra ilustrar o formato.

### Recompensa × Presente — dois conceitos diferentes

- **Presente** é o nome real que o TikTok usa (`Rose`, `TikTok`, `GG`,
  `Galaxy`...) — o que alguém manda de verdade na LIVE.
- **Recompensa** é a configuração (o conjunto de roupa, a duração, o
  revert etc.) — o que ela faz.

Como alguns presentes têm "o mesmo valor" pra você, **uma recompensa
pode ser disparada por mais de um presente**:

```yaml
gifts:
  Casual:                          # nome da recompensa (livre, não precisa ser nome de presente)
    gift_names: ["Rose", "TikTok", "GG"]   # qualquer um desses 3 dispara essa recompensa
    outfit: "Casual"
```

Cada presente real só pode disparar **uma** recompensa — se você tentar
colocar o mesmo presente em duas recompensas diferentes, o programa
recusa carregar e avisa exatamente o conflito.

> Se você não usar `gift_names`, a própria chave da recompensa é tratada
> como o nome do presente (é assim que configs mais simples/antigas
> continuam funcionando sem precisar editar nada):
> ```yaml
> gifts:
>   Rose:              # aqui "Rose" é ao mesmo tempo o nome da recompensa E o presente
>     parameter: "Outfit"
>     type: int
>     value: 1
> ```

Na GUI, isso é a aba **"Recompensas"**: o formulário de "Nova
recompensa" tem o nome livre da recompensa + uma lista separada de
"Presentes do TikTok que disparam esta recompensa" (com "Adicionar",
"Escolher da lista..." e "Remover selecionado").

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
- Uma recompensa pode disparar **mais de um alvo** de uma vez usando a
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
2. **Revert próprio da recompensa**, com `revert_outfit:` (nome de um
   conjunto) e/ou `revert:` (lista manual, mesmo formato de
   `parameters:`) — útil se, por exemplo, uma recompensa também ligou um
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

Se uma recompensa tiver duração e **nenhum dos dois** (nem revert próprio
nem o padrão global), o programa recusa carregar o `config.yaml` e
explica exatamente o que falta — assim nunca fica uma recompensa "presa"
sem saber para onde voltar.

Na GUI, tudo isso é configurável com o mouse: o formulário de recompensa
tem um menu suspenso pra escolher o conjunto a vestir, uma caixinha
"Esta recompensa fica ativa por um tempo..." + campo de duração com
escolha de unidade (**minutos** ou **segundos** — útil pra durações
curtas tipo 2 ou 5 segundos, sem precisar calcular frações de minuto)
+ um menu suspenso pra escolher o conjunto de revert. O padrão global
é definido na aba "Conjuntos de roupa" (botão "★ Definir como roupa
padrão").

### Ignorar a fila (`ignore_queue`) — pra ações que não devem esperar

Por padrão, toda recompensa **com duração** entra na fila exclusiva
acima — só um fica ativo por vez. Isso é o certo pra troca de roupa
(não faz sentido vestir duas coisas ao mesmo tempo), mas nem toda
recompensa com duração é uma troca de roupa: por exemplo, um "boop" no
nariz do avatar (liga um parâmetro, espera um instante, desliga) não
deveria ficar esperando 10 minutos atrás de uma troca de roupa em
andamento — ele deveria acontecer na hora, em paralelo.

Pra isso, marque `ignore_queue: true` na recompensa:

```yaml
gifts:
  Rose:
    parameter: "NOSE_BOOP"
    type: bool
    value: true
    duration_seconds: 2
    ignore_queue: true
    revert:
      - parameter: "NOSE_BOOP"
        type: bool
        value: false
```

Essa recompensa aplica, espera 2 segundos e reverte **sozinha**, sem
entrar na fila de troca de roupa nem esperar (ou bloquear) nenhuma
outra recompensa com duração. Na GUI, é a caixinha "Ignorar a fila"
dentro da seção de duração do formulário de recompensa.

Pra acompanhar o que está acontecendo na fila (a de troca de roupa,
não os `ignore_queue`), use os botões sempre visíveis:

- **"Ver fila..."**: mostra a recompensa ativa agora (com tempo restante
  aproximado) e a lista de quem está esperando.
- **"Limpar fila"**: cancela tudo (ativo + pendentes) sem reverter
  automaticamente, e avisa quantos foram removidos (ex: "2 recompensa(s)
  removida(s) da fila."). Se quiser que reverta pra roupa padrão
  também, use o **PÂNICO** em vez disso — ele limpa a fila (inclusive
  os `ignore_queue` que estiverem rodando), volta pra roupa padrão, e
  avisa quantas recompensas foram canceladas no total.

### Ativar/desativar uma recompensa sem apagar

Se você quer "desligar" uma recompensa temporariamente (por exemplo,
durante uma promoção diferente, ou pra testar algo sem que ela
dispare), não precisa apagar a configuração toda — marque
`enabled: false`:

```yaml
gifts:
  Rose:
    parameter: "Outfit"
    type: int
    value: 5
    enabled: false   # a recompensa continua configurada, mas é ignorada
```

Uma recompensa desativada aparece na lista principal acinzentada, com
"Não" na coluna "Ativo?". Se alguém mandar um presente que dispara essa
recompensa enquanto ela estiver desativada, o programa só loga que
ignorou, sem fazer nada. Na GUI, use o botão **"Ativar/Desativar"** na
aba "Recompensas" (com a recompensa selecionada) pra alternar isso com
um clique, sem precisar abrir o formulário de edição.

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
2. Clique em **"Parâmetros do avatar..."** (sempre visível, fora das
   abas) ou, direto de dentro do formulário de um alvo, no botão
   **"Escolher da lista do avatar..."** ao lado do campo de nome. Ela
   lê esse arquivo e mostra uma tabela com **todos** os parâmetros:
   nome, endereço OSC, tipo, e se dá pra "setar" ele de fora (alguns
   parâmetros são só de leitura — ex: velocidade — e não servem pra
   trocar roupa).
3. Tem um campo **"Filtrar"** no topo da tabela — útil se o avatar tem
   muitos parâmetros: digite parte do nome ou do endereço e a lista
   filtra na hora (mostra "N de M" pra você saber quantos bateram).
4. Selecione uma linha (ou dê duplo-clique) e use **"Copiar nome"** /
   **"Copiar endereço"** para colar depois num alvo, ou
   **"Usar este parâmetro..."** — se você abriu esta tela a partir de
   um formulário de alvo, isso preenche o nome e o tipo **direto
   naquele formulário**, sem precisar copiar/colar nada.

> Essa leitura só funciona no Windows (onde o VRChat roda) e só depois
> que o avatar foi carregado pelo menos uma vez com OSC habilitado. Se
> o VRChat nunca gerou esse arquivo ainda, a tela avisa e você pode
> continuar digitando os parâmetros manualmente normalmente.

### Descobrir o "significado" de cada valor (modo escuta)

O arquivo que o VRChat gera diz o **nome**, o **endereço** e o **tipo**
de cada parâmetro — mas não diz o que cada *valor* representa
visualmente. É comum um avatar ter, por exemplo, um único parâmetro
`OUTFIT` (Int) que troca entre "Casual", "Formal", "Jeans", "Maid" etc.
dependendo do número (`0`, `1`, `2`, `3`...) — esses nomes só existem
dentro do menu de expressões do VRChat, montado no projeto Unity de
quem criou o avatar; não tem como descobrir isso só lendo o arquivo.

Pra descobrir isso na prática, use **"Descobrir valores ao vivo..."**
(sempre visível, junto dos outros botões de ação):

1. Clique em **"Iniciar escuta"** (porta padrão: **9001** — é a porta
   que o próprio VRChat usa para *enviar* dados pra fora; diferente da
   9000, que é onde ele *recebe* comandos).
2. No VRChat, abra o menu de expressões e clique nas opções que você
   quer identificar (ex: troque o "Outfit" para "Maid").
3. O valor exato que o jogo mandou aparece na tela na hora — uma linha
   por parâmetro, sempre mostrando o **valor mais recente** (não uma
   lista que cresce sem parar, então parâmetros barulhentos como
   `Viseme` ou de movimento não enchem a tela).
4. Tem um filtro também, e um botão **"Usar como alvo..."** que abre
   um alvo já preenchido com o endereço, tipo e valor exatos que
   acabaram de chegar — pronto pra usar num presente ou conjunto.

> Isso é a mesma ideia da "segunda parte" que ferramentas como o
> Interfuse mostram: parâmetros com múltiplas opções escondidas atrás
> de um número, que só dá pra identificar vendo o valor mudar ao vivo.

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
  próprio nem roupa padrão global. Configure um dos dois (dentro do
  presente, ou na aba "Conjuntos de roupa" com "★ Definir como roupa padrão").
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

Com a LIVE já no ar e o VRChat aberto com OSC habilitado, clique em
"Conectar na LIVE" na GUI.

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
├── app.py                  # Ponto de entrada da GUI
├── iniciar_app.bat          # Atalho Windows: cria .venv + roda app.py
├── build_exe.bat            # Gera o TikTokVRChatBridge.exe standalone
├── tiktok_vrchat.spec        # Configuração do PyInstaller (usada pelo build_exe.bat)
├── BUILD.md                  # Como gerar o .exe manualmente (sem precisar de Python pra usar)
├── config.yaml              # Recompensas -> parâmetros OSC + config do VRChat
├── requirements.txt
├── requirements-dev.txt      # Só pra gerar o .exe (PyInstaller) -- não precisa pra usar
├── utils_log.py             # Logging padronizado [TIKTOK]/[OSC]/[ERROR]
├── config/
│   └── loader.py              # Carrega, valida e salva config.yaml
├── gui/
│   ├── app.py                 # Janela principal (Tkinter)
│   └── dialogs.py              # Diálogos de criar/editar recompensa + botão "Testar"
├── tiktok/
│   ├── listener.py            # Conexão TikTok LIVE + reconexão + streaks
│   └── catalog.py              # Lista de nomes de presente (LIVE + sugestões)
├── vrchat/
│   ├── osc.py                   # Cliente OSC para o VRChat
│   ├── osc_listener.py           # "Modo escuta": recebe o que o VRChat manda pra fora
│   └── discovery.py              # Lê os parâmetros do avatar gravados pelo VRChat
├── handlers/
│   ├── gifts.py               # Presente -> recompensa -> ação OSC (via config.yaml)
│   └── timed_queue.py          # Fila exclusiva de recompensas com duração
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
