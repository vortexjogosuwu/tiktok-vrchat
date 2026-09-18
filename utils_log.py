"""
utils_log.py

Logging padronizado no formato pedido:
[TIKTOK] ...
[OSC] ...
[ERROR] ...

Sempre imprime no console. Além disso, qualquer interface (como a GUI)
pode se inscrever via `add_sink(callback)` para também receber cada
linha de log e mostrá-la em um widget próprio.
"""

from __future__ import annotations

import datetime as _dt
from typing import Callable, List

SinkCallback = Callable[[str, str], None]  # (tag, message)

_sinks: List[SinkCallback] = []


def add_sink(callback: SinkCallback) -> None:
    """Registra um callback que recebe (tag, message) para cada log emitido."""
    _sinks.append(callback)


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%H:%M:%S")


def log(tag: str, message: str) -> None:
    print(f"[{_timestamp()}] [{tag}] {message}", flush=True)
    for sink in _sinks:
        try:
            sink(tag, message)
        except Exception:  # noqa: BLE001 - um sink com bug não pode derrubar o log
            pass


def log_tiktok(message: str) -> None:
    log("TIKTOK", message)


def log_osc(message: str) -> None:
    log("OSC", message)


def log_error(message: str) -> None:
    log("ERROR", message)
