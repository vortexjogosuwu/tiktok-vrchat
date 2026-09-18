"""
main.py

Ponto de entrada: TikTok LIVE (GiftEvent) -> VRChat (OSC).

Uso:
    python main.py
    python main.py --config outro_config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from config.loader import ConfigError, load_config
from handlers.gifts import GiftHandler
from tiktok.listener import TikTokGiftListener
from utils_log import log_error, log_tiktok
from vrchat.osc import VRChatOSC


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok LIVE -> VRChat OSC bridge")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Caminho para o arquivo de configuração (padrão: config.yaml)",
    )
    return parser.parse_args()


async def async_main(config_path: str) -> None:
    config = load_config(config_path)

    log_tiktok(f"Configuração carregada: @{config.tiktok_username} -> "
               f"OSC {config.osc_host}:{config.osc_port}")
    log_tiktok(f"{len(config.gifts)} presente(s) mapeado(s) no config.yaml")

    for warning in config.warnings:
        log_error(f"[CONFIG] {warning}")

    osc_client = VRChatOSC(host=config.osc_host, port=config.osc_port)
    gift_handler = GiftHandler(config=config, osc_client=osc_client)

    listener = TikTokGiftListener(
        username=config.tiktok_username,
        on_gift=gift_handler.handle_gift,
        reconnect_initial_delay=config.reconnect_initial_delay,
        reconnect_max_delay=config.reconnect_max_delay,
        reconnect_backoff_multiplier=config.reconnect_backoff_multiplier,
    )

    await listener.run_forever()


def main() -> None:
    args = parse_args()

    try:
        asyncio.run(async_main(args.config))
    except ConfigError as exc:
        log_error(f"Configuração inválida: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        log_tiktok("Encerrado pelo usuário (Ctrl+C).")
        sys.exit(0)


if __name__ == "__main__":
    main()
