"""
handlers/gifts.py

Ponte entre o evento "presente recebido" (vindo do tiktok/listener.py)
e o envio de mensagens OSC (vrchat/osc.py), usando o mapeamento
definido pelo usuário em config.yaml (carregado por config/loader.py).

Este é o único lugar do projeto que decide "qual presente faz o quê" —
e essa decisão vem inteiramente do arquivo de configuração (endereço,
tipo e valor totalmente livres), nunca de valores fixos no código.
"""

from __future__ import annotations

from config.loader import AppConfig
from utils_log import log_tiktok
from vrchat.osc import VRChatOSC


class GiftHandler:
    def __init__(self, config: AppConfig, osc_client: VRChatOSC) -> None:
        self.config = config
        self.osc_client = osc_client

    async def handle_gift(self, gift_name: str, user_name: str, quantity: int) -> None:
        rule = self.config.gifts.get(gift_name)

        if rule is None:
            # Presente recebido mas sem mapeamento no config.yaml.
            # Isso não é um erro: apenas avisamos e ignoramos.
            log_tiktok(
                f"Presente '{gift_name}' não está mapeado no config.yaml — ignorando."
            )
            return

        log_tiktok(
            f"Aplicando regra do presente '{gift_name}' (recebido de {user_name}, "
            f"quantidade {quantity})"
        )
        for target in rule.targets:
            self.osc_client.send(target.address, target.value)
