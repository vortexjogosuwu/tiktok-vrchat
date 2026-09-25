# -*- mode: python ; coding: utf-8 -*-
#
# Especificação do PyInstaller para empacotar o TikTok LIVE -> VRChat
# OSC Bridge como um .exe standalone (Windows), sem exigir Python
# instalado na máquina de quem vai usar.
#
# Como gerar o .exe:
#   1. No Windows, com o venv do projeto ativado:
#        pip install -r requirements.txt
#        pip install pyinstaller
#   2. Rode:
#        pyinstaller tiktok_vrchat.spec
#   3. O .exe fica em dist/TikTokVRChatBridge.exe
#
# (Ou simplesmente dê dois cliques em build_exe.bat, que faz tudo isso
# automaticamente. Veja BUILD.md para mais detalhes.)

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Algumas bibliotecas (principalmente a TikTokLive e suas dependências
# de rede) fazem import dinâmico de submódulos que o PyInstaller não
# detecta sozinho analisando o código -- por isso coletamos elas por
# completo, em vez de confiar só na análise estática.
_collect_names = [
    "TikTokLive",
    "pythonosc",
    "websockets",
    "protobuf",
    "google.protobuf",
]

hiddenimports = []
datas = []
binaries = []
for _name in _collect_names:
    try:
        _datas, _binaries, _hidden = collect_all(_name)
        datas += _datas
        binaries += _binaries
        hiddenimports += _hidden
    except Exception:
        # Se algum desses pacotes não existir no ambiente de build,
        # ignora -- o PyInstaller ainda tenta a análise estática normal.
        pass

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TikTokVRChatBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
