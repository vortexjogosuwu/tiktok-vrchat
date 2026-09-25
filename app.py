"""
app.py

Ponto de entrada da versao com interface grafica (janela, mouse) do
TikTok LIVE -> VRChat OSC Bridge.

Uso:
    python app.py
    python app.py --config outro_config.yaml

Funciona tanto rodando com "python app.py" quanto empacotado como um
.exe standalone (via PyInstaller) -- veja BUILD.md.
"""

from __future__ import annotations

import argparse
import os
import sys

from gui.app import run


def _default_base_dir() -> str:
    """
    Pasta onde procurar o config.yaml por padrao.

    Quando rodando como .exe empacotado (PyInstaller), usa a pasta onde
    o .exe está (não a pasta temporária onde ele se descompacta) --
    assim o config.yaml fica sempre ao lado do programa, de onde quer
    que você o execute (duplo-clique, atalho, linha de comando etc.).
    Quando rodando como script Python normal, usa a pasta deste arquivo.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok LIVE -> VRChat OSC bridge (GUI)")
    parser.add_argument(
        "--config",
        default=None,
        help="Caminho para o arquivo de configuracao (padrao: config.yaml ao lado do programa)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config_path = args.config or os.path.join(_default_base_dir(), "config.yaml")
    run(config_path=config_path)
