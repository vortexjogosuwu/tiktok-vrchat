"""
handlers/timed_queue.py

Fila de acoes OSC "exclusivas com duracao" -- por exemplo, um presente
que troca a roupa por alguns minutos e depois volta ao normal.

Regras implementadas:
- Um presente com duracao fica ATIVO por um tempo configuravel.
- Se outro presente com duracao chegar enquanto o atual ainda esta
  ativo, ele NAO sobrepoe: entra na fila (FIFO) e espera sua vez --
  A MENOS que o presente tenha `ignore_queue: true`, caso em que roda
  em paralelo, sem entrar nessa fila nem esperar nada (ver
  handlers/gifts.py).
- Quando o presente ativo termina, o programa manda os valores de
  "revert" (roupa padrao) automaticamente, e so depois libera o
  proximo da fila (se houver).
- pending_snapshot() / current_snapshot() -- pra GUI mostrar "o que
  esta na fila agora" sem mexer em nada.
- panic_clear() -- limpa tudo (fila + o que estiver ativo agora) sem
  rodar o revert de ninguem, e RETORNA quantos itens foram descartados
  (pra GUI informar "N presentes removidos da fila").
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from config.loader import OscTarget
from utils_log import log_error, log_tiktok
from vrchat.osc import VRChatOSC, send_target_sequence


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
    started_at: float | None = None


@dataclass
class QueueItemInfo:
    gift_name: str
    user_name: str
    duration_seconds: float
    remaining_seconds: float | None = None  # None = ainda nao comecou (na fila)


class TimedActionQueue:
    """
    Fila FIFO de acoes exclusivas com duracao, processadas uma de cada vez
    dentro do event loop assincrono em que `enqueue()` for chamado pela
    primeira vez.
    """

    def __init__(self, osc_client: VRChatOSC) -> None:
        self.osc_client = osc_client
        # Lista simples em vez de asyncio.Queue -- assim dá pra "espiar"
        # o que está esperando (pending_snapshot) sem precisar remover.
        self._pending: list[_QueuedAction] = []
        self._current: _QueuedAction | None = None
        self._new_item_event: "asyncio.Event | None" = None
        self._worker_task = None

    def _ensure_ready(self) -> None:
        if self._new_item_event is None:
            self._new_item_event = asyncio.Event()
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

        if self._current is not None or self._pending:
            position = len(self._pending) + 1
            log_tiktok(
                f"'{gift_name}' (de {user_name}) entrou na fila "
                f"(posicao {position}) -- aguardando o presente atual terminar."
            )

        self._pending.append(
            _QueuedAction(
                gift_name=gift_name,
                user_name=user_name,
                targets=targets,
                duration_seconds=duration_seconds,
                revert_targets=revert_targets,
            )
        )
        self._new_item_event.set()

    async def _worker(self) -> None:
        while True:
            if not self._pending:
                self._new_item_event.clear()
                await self._new_item_event.wait()
                continue

            action = self._pending.pop(0)
            action.started_at = time.monotonic()
            self._current = action
            try:
                log_tiktok(
                    f"Ativando '{action.gift_name}' (de {action.user_name}) "
                    f"por {_format_duration(action.duration_seconds)} -- "
                    f"{len(action.targets)} alvo(s), revert com "
                    f"{len(action.revert_targets)} alvo(s)"
                )
                await send_target_sequence(self.osc_client, action.targets)

                await asyncio.sleep(action.duration_seconds)

                if action.revert_targets:
                    log_tiktok(
                        f"Tempo de '{action.gift_name}' esgotado -- voltando a roupa padrao"
                    )
                    await send_target_sequence(self.osc_client, action.revert_targets)
                else:
                    log_error(
                        f"Tempo de '{action.gift_name}' esgotado, mas NÃO havia "
                        f"nenhum alvo de revert configurado -- nada foi enviado "
                        f"e o avatar continua com a roupa que foi aplicada."
                    )
            except asyncio.CancelledError:
                # Interrompido (ex: botão de PÂNICO/Limpar fila) -- não
                # roda o revert deste item, quem cancelou decide o que fazer.
                log_tiktok(f"'{action.gift_name}' foi interrompido antes de terminar.")
                raise
            except Exception as exc:  # noqa: BLE001
                log_error(f"Erro processando fila de '{action.gift_name}': {exc}")
            finally:
                self._current = None

    async def panic_clear(self) -> int:
        """
        Descarta tudo que estava esperando na fila e interrompe o que
        estiver ativo agora NA HORA (sem deixar ele mandar seu próprio
        revert -- quem chamou isso decide o que fazer depois, ex: mandar
        um revert manual). Retorna quantos itens foram descartados no
        total (pendentes + o que estava ativo, se houver).
        """
        discarded = len(self._pending)
        self._pending.clear()

        if self._current is not None:
            discarded += 1

        if self._worker_task is not None and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        self._current = None

        if discarded:
            log_tiktok(f"Fila limpa: {discarded} presente(s) descartado(s).")

        return discarded

    def pending_snapshot(self) -> list[QueueItemInfo]:
        """Itens esperando na fila agora (não inclui o que está ativo)."""
        return [
            QueueItemInfo(
                gift_name=a.gift_name, user_name=a.user_name,
                duration_seconds=a.duration_seconds, remaining_seconds=None,
            )
            for a in self._pending
        ]

    def current_snapshot(self) -> QueueItemInfo | None:
        """O item ativo agora, com o tempo restante aproximado (ou None)."""
        action = self._current
        if action is None:
            return None
        remaining = None
        if action.started_at is not None:
            elapsed = time.monotonic() - action.started_at
            remaining = max(0.0, action.duration_seconds - elapsed)
        return QueueItemInfo(
            gift_name=action.gift_name, user_name=action.user_name,
            duration_seconds=action.duration_seconds, remaining_seconds=remaining,
        )

    def pending_count(self) -> int:
        """Quantos itens estao esperando na fila (nao conta o que esta ativo agora)."""
        return len(self._pending)

    def is_busy(self) -> bool:
        return self._current is not None
