"""
vrchat/osc.py

Camada de comunicação com o VRChat (ou qualquer app compatível) via OSC.

Este módulo usa a biblioteca `python-osc` (pythonosc.udp_client.SimpleUDPClient),
que é a forma padrão e documentada de enviar mensagens OSC via UDP em Python.
Referência: https://python-osc.readthedocs.io/en/latest/client.html

O endereço OSC final (ex: "/avatar/parameters/Outfit") já vem pronto de
config/loader.py — este módulo não assume nenhum prefixo fixo, então
funciona tanto para parâmetros de avatar quanto para qualquer outro
endereço OSC que você queira customizar no config.yaml.
"""

from __future__ import annotations

from typing import Any

from pythonosc.udp_client import SimpleUDPClient

from utils_log import log_error, log_osc


class VRChatOSC:
    """Cliente OSC simples e resiliente."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._client: SimpleUDPClient | None = None
        self._connect()

    def _connect(self) -> None:
        # SimpleUDPClient não abre conexão TCP nenhuma (OSC via VRChat é UDP,
        # não orientado a conexão), então isso apenas prepara o socket local.
        self._client = SimpleUDPClient(self.host, self.port)

    def send(self, address: str, value: Any) -> bool:
        """
        Envia `value` para o endereço OSC `address` (ex: "/avatar/parameters/Outfit").

        `value` já deve vir com o tipo Python correto (int, float, bool ou str) —
        isso é resolvido em config/loader.py a partir do campo `type` do YAML.

        Retorna True em caso de sucesso, False em caso de falha
        (e registra a falha em log, sem derrubar o programa).
        """
        try:
            if self._client is None:
                self._connect()
            self._client.send_message(address, value)  # type: ignore[union-attr]
            log_osc(f"{address} = {value!r}")
            return True
        except OSError as exc:
            log_error(f"Não foi possível enviar OSC para o VRChat ({exc})")
            # Força reconstrução do socket na próxima tentativa
            self._client = None
            return False
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o app aqui
            log_error(f"Falha inesperada ao enviar OSC: {exc}")
            return False
