"""
app.py

Ponto de entrada da versao com interface grafica (janela, mouse) do
TikTok LIVE -> VRChat OSC Bridge.

Uso:
    python app.py
    python app.py --config outro_config.yaml
"""

from __future__ import annotations

import argparse

from gui.app import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok LIVE -> VRChat OSC bridge (GUI)")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Caminho para o arquivo de configuracao (padrao: config.yaml)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(config_path=args.config)
