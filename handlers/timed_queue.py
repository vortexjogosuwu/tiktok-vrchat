"""
handlers/timed_queue.py

Fila de acoes OSC "exclusivas com duracao" -- por exemplo, um presente
que troca a roupa por alguns minutos e depois volta ao normal.

Regras implementadas (conforme pedido):
- Um presente com duracao fica ATIVO por um tempo configuravel.
- Se outro presente com duracao chegar enquanto o atual ainda esta
  ativo, ele NAO sobrepoe: entra na fila (FIFO) e espera sua vez.
- Quando o presente ativo termina, o programa manda os valores de
  "revert" (roupa padrao) automaticamente, e so depois libera o
  proximo da fila (se houver).
- Se a fila estiver vazia quando um termina, o avatar simplesmente
  fica na roupa padrao ate o proximo presente com duracao chegar.

Presentes SEM duracao configurada nao passam por esta fila -- eles
continuam disparando na hora, em paralelo, exatamente como antes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config.loader import OscTarget
from utils_log import log_error, log_tiktok
from vrchat.osc import VRChatOSC


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        if seconds == int(seconds):
            return f"{int(seconds)}s"
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes == int(minutes):
        return f"{int(minutes)} min"
    return f"{minutes:.1f} min"


@dataclass
class _QueuedAction:
    gift_name: str
    user_name: str
    targets: list
    duration_seconds: float
    revert_targets: list


class TimedActionQueue:
    """
    Fila FIFO de acoes exclusivas com duracao, processadas uma de cada vez
    dentro do event loop assincrono em que `enqueue()` for chamado pela
    primeira vez.
    """

    def __init__(self, osc_client: VRChatOSC) -> None:
        self.osc_client = osc_client
        # A fila é criada sob demanda, dentro de enqueue() -- ou seja,
        # sempre a partir do event loop assíncrono correto (o da conexão
        # com o TikTok). Criar o asyncio.Queue() cedo demais, fora desse
        # loop, pode causar problemas sutis de "loop errado" dependendo
        # da versão do Python.
        self._queue: "asyncio.Queue | None" = None
        self._worker_task = None
        self._busy = False

    def _ensure_ready(self) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, gift_name, user_name, targets, duration_seconds, revert_targets):
        self._ensure_ready()

        if not revert_targets:
            log_error(
                f"[CONFIG] '{gift_name}' tem duração mas a lista de revert está "
                f"vazia no momento em que o presente chegou — o avatar NÃO vai "
                f"voltar sozinho ao final do tempo. Confira o presente na GUI: "
                f"ele precisa de um conjunto de revert, alvos extras de revert, "
                f"ou uma 'Roupa padrão (revert global)' configurada."
            )

        if self._busy or not self._queue.empty():
            position = self._queue.qsize() + 1
            log_tiktok(
                f"'{gift_name}' (de {user_name}) entrou na fila "
                f"(posicao {position}) -- aguardando o presente atual terminar."
            )

        await self._queue.put(
            _QueuedAction(
                gift_name=gift_name,
                user_name=user_name,
                targets=targets,
                duration_seconds=duration_seconds,
                revert_targets=revert_targets,
            )
        )

    async def _worker(self) -> None:
        while True:
            action = await self._queue.get()
            self._busy = True
            try:
                log_tiktok(
                    f"Ativando '{action.gift_name}' (de {action.user_name}) "
                    f"por {_format_duration(action.duration_seconds)} -- "
                    f"{len(action.targets)} alvo(s), revert com "
                    f"{len(action.revert_targets)} alvo(s)"
                )
                for target in action.targets:
                    self.osc_client.send(target.address, target.value)

                await asyncio.sleep(action.duration_seconds)

                if action.revert_targets:
                    log_tiktok(
                        f"Tempo de '{action.gift_name}' esgotado -- voltando a roupa padrao"
                    )
                    for target in action.revert_targets:
                        self.osc_client.send(target.address, target.value)
                else:
                    log_error(
                        f"Tempo de '{action.gift_name}' esgotado, mas NÃO havia "
                        f"nenhum alvo de revert configurado -- nada foi enviado "
                        f"e o avatar continua com a roupa que foi aplicada."
                    )
            except Exception as exc:  # noqa: BLE001
                log_error(f"Erro processando fila de '{action.gift_name}': {exc}")
            finally:
                self._busy = False
                self._queue.task_done()

    def pending_count(self) -> int:
        """Quantos itens estao esperando na fila (nao conta o que esta ativo agora)."""
        return self._queue.qsize() if self._queue is not None else 0

    def is_busy(self) -> bool:
        return self._busy
