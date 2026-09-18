"""
handlers/gifts.py

Ponte entre o evento "presente recebido" (vindo do tiktok/listener.py)
e o envio de mensagens OSC (vrchat/osc.py), usando o mapeamento
definido pelo usuario em config.yaml (carregado por config/loader.py).

Presentes SEM duracao configurada disparam na hora (como sempre).
Presentes COM duracao configurada (duration_minutes/duration_seconds)
passam pela fila exclusiva em handlers/timed_queue.py: so um fica
ativo por vez, os outros esperam a vez deles, e ao final do tempo o
avatar volta para a roupa padrao (revert do proprio presente, ou o
'vrchat.default_revert' global).
"""

from __future__ import annotations

from config.loader import AppConfig
from handlers.timed_queue import TimedActionQueue
from utils_log import log_tiktok
from vrchat.osc import VRChatOSC


class GiftHandler:
    def __init__(self, config: AppConfig, osc_client: VRChatOSC) -> None:
        self.config = config
        self.osc_client = osc_client
        self.timed_queue = TimedActionQueue(osc_client)

    async def handle_gift(self, gift_name: str, user_name: str, quantity: int) -> None:
        rule = self.config.gifts.get(gift_name)

        if rule is None:
            # Presente recebido mas sem mapeamento no config.yaml.
            # Isso nao e um erro: apenas avisamos e ignoramos.
            log_tiktok(
                f"Presente '{gift_name}' não está mapeado no config.yaml — ignorando."
            )
            return

        if rule.duration_seconds is not None:
            revert_targets = rule.effective_revert_targets(self.config.default_revert)
            revert_source = (
                "revert próprio do presente" if rule.revert_targets
                else ("padrão global" if revert_targets else "NENHUM configurado")
            )
            revert_preview = ", ".join(
                f"{t.address}={t.value!r}" for t in revert_targets
            ) or "(vazio)"
            log_tiktok(
                f"'{gift_name}' (de {user_name}, quantidade {quantity}) é um presente "
                f"com duração — enviando para a fila. Revert ({revert_source}): "
                f"{revert_preview}"
            )
            await self.timed_queue.enqueue(
                gift_name=gift_name,
                user_name=user_name,
                targets=rule.targets,
                duration_seconds=rule.duration_seconds,
                revert_targets=revert_targets,
            )
            return

        log_tiktok(
            f"Aplicando regra do presente '{gift_name}' (recebido de {user_name}, "
            f"quantidade {quantity})"
        )
        for target in rule.targets:
            self.osc_client.send(target.address, target.value)
