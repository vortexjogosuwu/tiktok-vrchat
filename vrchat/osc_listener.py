"""
vrchat/osc_listener.py

"Modo escuta": um servidor OSC passivo que escuta o que o PROPRIO
VRChat manda para fora (porta padrao 9001) sempre que um parametro do
avatar muda -- por exemplo, ao trocar de roupa/acessorio pelo menu de
expressoes do jogo.

Serve para descobrir, na pratica, qual numero corresponde a qual opcao
visual (ex: qual valor de OUTFIT e "Casual", "Formal", "Maid" etc) sem
precisar adivinhar. Essa informacao (o "significado" de cada valor) so
existe no projeto Unity de quem criou o avatar -- o OSC em si so sabe
o nome tecnico, o tipo e o valor atual de cada parametro.

Referencia oficial: https://docs.vrchat.com/docs/osc-overview
("VRChat, we default to receiving on port 9000 and sending on port 9001")
"""

from __future__ import annotations

from typing import Callable, Optional

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

# Porta padrao que o VRChat usa para ENVIAR dados pra fora (diferente
# da porta 9000, que e onde ele RECEBE comandos -- essa e a mesma que
# vrchat.osc_port no config.yaml).
DEFAULT_LISTEN_PORT = 9001

MessageCallback = Callable[[str, tuple], None]


class VRChatOscListener:
    """
    Escuta mensagens OSC vindas do VRChat e chama `on_message(address,
    args)` para cada uma. Precisa ser iniciado (`start()`) dentro de um
    event loop assincrono ativo, e parado (`stop()`) explicitamente.
    """

    def __init__(
        self,
        on_message: MessageCallback,
        host: str = "0.0.0.0",
        port: int = DEFAULT_LISTEN_PORT,
    ) -> None:
        self.on_message = on_message
        self.host = host
        self.port = port
        self._transport = None

    async def start(self) -> None:
        import asyncio

        if self._transport is not None:
            return  # ja rodando

        loop = asyncio.get_running_loop()
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._handle)
        server = AsyncIOOSCUDPServer((self.host, self.port), dispatcher, loop)
        self._transport, _protocol = await server.create_serve_endpoint()

    def _handle(self, address: str, *args) -> None:
        try:
            self.on_message(address, args)
        except Exception:  # noqa: BLE001 - nunca deixar um erro aqui derrubar nada
            pass

    async def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @property
    def is_running(self) -> bool:
        return self._transport is not None
