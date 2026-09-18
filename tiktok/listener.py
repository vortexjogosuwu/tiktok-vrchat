"""
tiktok/listener.py

Conexão com a LIVE do TikTok usando a biblioteca `TikTokLive`
(https://github.com/isaackogan/TikTokLive).

Não é necessário login nem senha: basta o @username do canal.
A conexão é feita via WebSocket contra o serviço Webcast do TikTok.

Responsabilidades deste módulo:
- Conectar/reconectar na LIVE (com backoff exponencial);
- Traduzir GiftEvent em uma chamada de callback simples e já
  "deduplicada" de streak (ver `_should_trigger`);
- Nunca derrubar o processo por causa de uma desconexão temporária;
- Permitir ser parado de fora (ex: botão "Desconectar" na GUI), mesmo
  vindo de outra thread.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, GiftEvent

from utils_log import log_error, log_tiktok

# Assinatura do callback chamado quando um presente deve, de fato,
# disparar uma ação (streak já finalizado, quando aplicável).
GiftCallback = Callable[[str, str, int], Awaitable[None]]

# Assinatura do callback de status, usado pela GUI para atualizar o
# indicador visual. Valores possíveis: "connecting", "connected",
# "disconnected", "stopped".
StatusCallback = Callable[[str], None]


def _should_trigger(event: GiftEvent) -> bool:
    """
    Decide se este GiftEvent deve disparar uma ação agora.

    Presentes "streakable" (ex: Rose) chegam várias vezes durante o combo,
    incrementando `repeat_count`. Só queremos agir quando o streak termina
    (`event.streaking == False`), usando o `repeat_count` final.

    Presentes não streakable disparam imediatamente, sempre uma única vez.
    """
    if event.gift.streakable:
        return not event.streaking
    return True


class TikTokGiftListener:
    def __init__(
        self,
        username: str,
        on_gift: GiftCallback,
        reconnect_initial_delay: float = 5,
        reconnect_max_delay: float = 60,
        reconnect_backoff_multiplier: float = 2,
        on_status: Optional[StatusCallback] = None,
    ) -> None:
        self.username = username
        self.on_gift = on_gift
        self.reconnect_initial_delay = reconnect_initial_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.reconnect_backoff_multiplier = reconnect_backoff_multiplier
        self.on_status = on_status or (lambda _status: None)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_client: Optional[TikTokLiveClient] = None
        self._stopping = False

    def _build_client(self) -> TikTokLiveClient:
        client = TikTokLiveClient(unique_id=f"@{self.username}")

        @client.on(ConnectEvent)
        async def on_connect(_: ConnectEvent) -> None:
            log_tiktok(f"Conectado à LIVE de @{self.username}")
            self.on_status("connected")

        @client.on(DisconnectEvent)
        async def on_disconnect(_: DisconnectEvent) -> None:
            log_tiktok("Desconectado da LIVE")
            self.on_status("disconnected")

        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent) -> None:
            gift_name = event.gift.name
            user_name = event.user.unique_id or event.user.nickname
            quantity = event.repeat_count if event.gift.streakable else 1

            if not _should_trigger(event):
                # Ainda dentro do combo: apenas log discreto, sem disparar ação
                log_tiktok(
                    f"{user_name} está enviando {gift_name} (combo em andamento, "
                    f"x{event.repeat_count})"
                )
                return

            log_tiktok(f"{user_name} enviou {gift_name} x{quantity}")

            try:
                await self.on_gift(gift_name, user_name, quantity)
            except Exception as exc:  # noqa: BLE001
                log_error(f"Erro ao processar presente '{gift_name}': {exc}")

        return client

    async def run_forever(self) -> None:
        """
        Loop de conexão com reconexão automática e backoff exponencial.
        Nunca levanta exceção para fora: fica tentando reconectar
        indefinidamente até `request_stop()` ser chamado (ex: botão
        "Desconectar" na GUI, possivelmente vindo de outra thread).
        """
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        delay = self.reconnect_initial_delay

        while not self._stopping:
            client = self._build_client()
            self._current_client = client
            try:
                log_tiktok(f"Conectando à LIVE de @{self.username}...")
                self.on_status("connecting")
                # connect() é "future-blocking": aguarda dentro do event loop
                # assíncrono até a conexão cair (fim da LIVE, erro, parada manual, etc.)
                await client.connect()
                delay = self.reconnect_initial_delay
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log_error(f"Não foi possível conectar ao TikTok LIVE ({exc})")
                self.on_status("disconnected")
            finally:
                try:
                    await client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                self._current_client = None

            if self._stopping:
                break

            log_tiktok(f"Nova tentativa de conexão em {delay:.0f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * self.reconnect_backoff_multiplier, self.reconnect_max_delay)

        self.on_status("stopped")

    def request_stop(self) -> None:
        """
        Pede para o listener parar. Pode ser chamado de QUALQUER thread
        (ex: a thread da GUI), mesmo que run_forever() esteja rodando em
        outra thread com seu próprio event loop.
        """
        if self._loop is None:
            return

        def _do_stop() -> None:
            self._stopping = True
            if self._current_client is not None:
                asyncio.ensure_future(self._current_client.disconnect())

        self._loop.call_soon_threadsafe(_do_stop)
