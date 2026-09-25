"""
handlers/gifts.py

Ponte entre o evento "presente recebido" (vindo do tiktok/listener.py)
e o envio de mensagens OSC (vrchat/osc.py), usando o mapeamento
definido pelo usuario em config.yaml (carregado por config/loader.py).

Presentes SEM duracao configurada disparam na hora (como sempre).
Presentes COM duracao configurada (duration_minutes/duration_seconds)
passam pela fila exclusiva em handlers/timed_queue.py -- A MENOS que
tenham `ignore_queue: true`, caso em que rodam em PARALELO (aplicam,
esperam, revertem) sem entrar na fila nem esperar/bloquear outros
presentes com duracao. Bom para acoes rapidas (tipo um "boop" no
nariz) que nao devem ficar presas atras de uma troca de roupa longa.

Presentes com `enabled: false` sao ignorados quando chegam, sem
precisar apagar a configuracao.

Tambem expoe acoes manuais independentes da fila: voltar para a roupa
padrao na hora, e o "panico" (limpar a fila inteira + os presentes
paralelos ativos + voltar pra roupa padrao de uma vez).
"""

from __future__ import annotations

import asyncio

from config.loader import AppConfig
from handlers.timed_queue import TimedActionQueue
from utils_log import log_error, log_tiktok
from vrchat.osc import VRChatOSC, send_target_sequence


class GiftHandler:
    def __init__(self, config: AppConfig, osc_client: VRChatOSC) -> None:
        self.config = config
        self.osc_client = osc_client
        self.timed_queue = TimedActionQueue(osc_client)
        # Tarefas de presentes com `ignore_queue: true` atualmente em
        # andamento (aplicado, esperando a duração, ainda não reverteu).
        self._independent_tasks: set[asyncio.Task] = set()

    async def handle_gift(self, gift_name: str, user_name: str, quantity: int) -> None:
        """Chamado quando um presente REAL chega da LIVE do TikTok --
        acha a recompensa correspondente pelo nome do presente."""
        reward_name = self.config.gift_name_lookup.get(gift_name)

        if reward_name is None:
            # Presente recebido mas sem mapeamento a nenhuma recompensa.
            # Isso nao e um erro: apenas avisamos e ignoramos.
            log_tiktok(
                f"Presente '{gift_name}' não está mapeado a nenhuma recompensa — ignorando."
            )
            return

        await self._trigger_reward(reward_name, gift_name, user_name, quantity)

    async def test_reward(self, reward_name: str, user_name: str, quantity: int) -> None:
        """
        Testa uma recompensa DIRETO PELO NOME DELA (não precisa ser um
        presente real do TikTok -- é o nome que aparece na aba
        "Recompensas" da GUI). Usado pelos botões "Testar (Completo)"
        e afins, já que o nome da recompensa pode ser bem diferente dos
        presentes que a disparam.
        """
        if reward_name not in self.config.gifts:
            log_error(f"Recompensa '{reward_name}' não encontrada.")
            return
        await self._trigger_reward(reward_name, reward_name, user_name, quantity)

    async def _trigger_reward(
        self, reward_name: str, source_gift_name: str, user_name: str, quantity: int
    ) -> None:
        rule = self.config.gifts[reward_name]

        # Rótulo pra log: se a recompensa tem o mesmo nome do presente
        # que a disparou (caso comum, 1 presente = 1 recompensa), ou se
        # é um teste manual, não repete à toa.
        label = (
            reward_name if reward_name == source_gift_name
            else f"{reward_name} (via '{source_gift_name}')"
        )

        if not rule.enabled:
            log_tiktok(f"Recompensa '{label}' está desativada — ignorando.")
            return

        if rule.duration_seconds is not None:
            revert_targets = rule.effective_revert_targets(self.config.default_revert)
            revert_source = (
                "revert próprio da recompensa" if rule.revert_targets
                else ("padrão global" if revert_targets else "NENHUM configurado")
            )
            revert_preview = ", ".join(
                f"{t.address}={t.value!r}" for t in revert_targets
            ) or "(vazio)"
            fila_info = "ignorando a fila (roda em paralelo)" if rule.ignore_queue else "enviando para a fila"
            log_tiktok(
                f"'{label}' (de {user_name}, quantidade {quantity}) é uma recompensa "
                f"com duração — {fila_info}. Revert ({revert_source}): {revert_preview}"
            )

            if rule.ignore_queue:
                task = asyncio.create_task(
                    self._run_independent(
                        label, user_name, rule.targets, rule.duration_seconds, revert_targets
                    )
                )
                self._independent_tasks.add(task)
                task.add_done_callback(self._independent_tasks.discard)
            else:
                await self.timed_queue.enqueue(
                    gift_name=label,
                    user_name=user_name,
                    targets=rule.targets,
                    duration_seconds=rule.duration_seconds,
                    revert_targets=revert_targets,
                )
            return

        log_tiktok(
            f"Aplicando regra da recompensa '{label}' (recebido de {user_name}, "
            f"quantidade {quantity})"
        )
        await send_target_sequence(self.osc_client, rule.targets)

    async def _run_independent(
        self, gift_name, user_name, targets, duration_seconds, revert_targets
    ) -> None:
        """Aplica/espera/reverte um presente com `ignore_queue: true`,
        totalmente à parte da fila exclusiva -- não espera nem bloqueia
        nenhum outro presente com duração."""
        try:
            await send_target_sequence(self.osc_client, targets)
            await asyncio.sleep(duration_seconds)
            if revert_targets:
                log_tiktok(f"Tempo de '{gift_name}' (paralelo) esgotado — voltando ao padrão")
                await send_target_sequence(self.osc_client, revert_targets)
            else:
                log_error(
                    f"Tempo de '{gift_name}' (paralelo) esgotado, mas NÃO havia "
                    f"revert configurado — nada foi enviado."
                )
        except asyncio.CancelledError:
            log_tiktok(f"'{gift_name}' (paralelo) foi interrompido antes de terminar.")
            raise
        except Exception as exc:  # noqa: BLE001
            log_error(f"Erro processando '{gift_name}' (paralelo): {exc}")

    async def revert_to_default(self) -> None:
        """
        Manda os alvos da roupa padrão AGORA, direto -- sem passar pela
        fila. Usado pelo botão "Voltar para roupa padrão" e como parte
        do "PÂNICO". Não mexe em nenhum presente que esteja na fila (uma
        eventual ação já agendada ainda vai rodar seu próprio revert
        depois); para isso, use panic() em vez desta função.
        """
        if not self.config.default_revert:
            log_error(
                "Não há 'Roupa padrão (revert global)' configurada — nada para reverter."
            )
            return
        log_tiktok("Voltando para a roupa padrão (manual).")
        await send_target_sequence(self.osc_client, self.config.default_revert)

    async def panic(self) -> tuple[int, int]:
        """
        PÂNICO: cancela tudo que estiver ativo/esperando na fila de
        presentes com duração (inclusive os que rodam em paralelo com
        `ignore_queue: true`) e volta para a roupa padrão imediatamente.

        Retorna (itens_da_fila_removidos, presentes_paralelos_interrompidos).
        """
        log_tiktok("🚨 PÂNICO: limpando a fila de presentes e voltando à roupa padrão.")
        queue_cleared = await self.timed_queue.panic_clear()

        independent_cleared = len(self._independent_tasks)
        for task in list(self._independent_tasks):
            task.cancel()
        if self._independent_tasks:
            await asyncio.gather(*list(self._independent_tasks), return_exceptions=True)

        await self.revert_to_default()
        return queue_cleared, independent_cleared
