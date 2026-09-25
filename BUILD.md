# Gerando um .exe standalone (sem precisar de Python instalado)

Este projeto pode virar um único arquivo `TikTokVRChatBridge.exe` que
roda em qualquer PC Windows, mesmo sem Python instalado nele. Isso é
feito com o [PyInstaller](https://pyinstaller.org/), que empacota o
Python + todas as bibliotecas dentro do próprio `.exe`.

## Requisitos

- **Windows de verdade.** PyInstaller não faz cross-compile: pra gerar
  um `.exe` do Windows, o build precisa rodar num Windows (o seu PC,
  uma máquina virtual, etc.) — não dá pra gerar a partir de Linux/macOS.
- Python instalado nessa máquina (só pra *gerar* o `.exe` — quem for só
  *usar* o `.exe` depois não precisa de Python).

## Passo a passo

Dentro da pasta do projeto, no Windows:

```bash
build_exe.bat
```

Esse script faz tudo sozinho:

1. Cria (ou reaproveita) o ambiente virtual `.venv`.
2. Instala as dependências normais do programa **+** o PyInstaller
   (via `requirements-dev.txt` — isso é só pra quem está gerando o
   `.exe`; não afeta quem vai só *usar* ele depois).
3. Roda o PyInstaller usando a configuração em `tiktok_vrchat.spec`.
4. Deixa o resultado pronto em `dist\TikTokVRChatBridge.exe`.

Depois, copie `TikTokVRChatBridge.exe` pra qualquer pasta (junto com um
`config.yaml`, que ele procura do lado dele) — não precisa de Python
nem de mais nada instalado ali. Dá pra mandar esse `.exe` + o
`config.yaml` pra qualquer outra pessoa/PC Windows.

> Toda vez que você alterar o código e quiser uma versão nova do
> `.exe`, é só rodar `build_exe.bat` de novo — ele limpa o build
> anterior e gera um novo.

## Se a janela fechar rápido demais pra ler

O `build_exe.bat` grava **tudo** que acontece (cada passo, e qualquer
erro) num arquivo `build_log.txt`, criado na mesma pasta do projeto —
mesmo que a janela pisque e feche antes de você conseguir ler, o
conteúdo continua lá. Ele também mostra esse log inteiro na tela antes
de pedir "Pressione qualquer tecla" no final, então normalmente já dá
pra ver o que aconteceu sem precisar abrir o arquivo. Se mesmo assim
não der tempo de ler, abra `build_log.txt` num editor de texto (ou me
mande o conteúdo dele) pra identificar o erro exato.

## Como o `.exe` funciona por dentro

- É gerado em **modo "um arquivo só"** (`--onefile` no PyInstaller):
  tudo (Python + bibliotecas) fica dentro de um único `.exe`. Isso é o
  mais simples de distribuir, ao custo de abrir um pouquinho mais devagar
  (ele se descompacta numa pasta temporária toda vez que roda).
- O `config.yaml` é procurado **na mesma pasta onde está o `.exe`**,
  não numa pasta temporária — então dá pra mover o `.exe` pra qualquer
  lugar, contanto que o `config.yaml` vá junto.
- Ele já vem sem o "console" (janela preta de terminal) — só abre a
  interface gráfica normalmente.
- Tamanho aproximado: ~50 MB (a maior parte é o próprio interpretador
  Python + as bibliotecas de rede da TikTokLive).

## Se o `.exe` não funcionar

Como o build de verdade só roda no Windows (não consigo testar isso
por aqui — testei a configuração num Linux, que só confirma que a
receita do PyInstaller funciona, não substitui testar no Windows de
verdade), se o `.exe` gerado der erro ao abrir ou ao conectar na LIVE,
o jeito mais rápido de descobrir o motivo é gerar uma versão "com
console" temporariamente, pra ver a mensagem de erro:

1. Abra `tiktok_vrchat.spec` num editor de texto.
2. Troque `console=False` por `console=True`.
3. Rode `build_exe.bat` de novo.
4. Rode o `.exe` gerado — agora uma janela de terminal abre junto e
   mostra qualquer erro/traceback que aconteça.
5. Depois de resolver, troque `console=True` de volta pra `False` e
   gere a versão final.

Erros comuns nesse tipo de empacotamento costumam ser de "hidden
import" (uma biblioteca que faz import dinâmico de um jeito que o
PyInstaller não detecta sozinho) — se for isso, a mensagem de erro
geralmente diz `ModuleNotFoundError: No module named '...'`, e dá pra
resolver adicionando esse nome na lista `hiddenimports` dentro do
`tiktok_vrchat.spec`. Me manda a mensagem de erro exata que eu ajusto.
