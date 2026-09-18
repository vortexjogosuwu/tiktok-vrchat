"""
config/loader.py

Responsável por carregar e validar o arquivo config.yaml.
Nenhum outro módulo deve ler o YAML diretamente — tudo passa por aqui,
assim adicionar/alterar presentes nunca exige tocar em código Python.

Cada presente pode disparar um ou mais alvos OSC (`OscTarget`). Cada
alvo tem:
    - address: endereço OSC final (ex: "/avatar/parameters/Outfit")
    - value_type: "int" | "float" | "bool" | "string"
    - value: já convertido para o tipo Python correspondente

O tipo é sempre explícito no config.yaml (campo `type`) para evitar
ambiguidade: nem todos avatar usa os mesmos parâmetros, e alguns são
Int, outros Float, outros Bool — cada presente define exatamente o
que precisa, sem suposições escondidas no código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_TYPES = ("int", "float", "bool", "string")

# Endereço padrão para parâmetros de avatar do VRChat
AVATAR_PARAM_PREFIX = "/avatar/parameters/"

# Valores aceitos como "verdadeiro"/"falso" quando o YAML traz bool como texto
_TRUE_STRINGS = {"true", "1", "yes", "on", "sim"}
_FALSE_STRINGS = {"false", "0", "no", "off", "nao", "não"}


class ConfigError(Exception):
    """Erro de configuração inválida ou arquivo ausente."""


@dataclass
class OscTarget:
    address: str
    value_type: str
    value: Any


@dataclass
class GiftRule:
    gift_name: str
    targets: list[OscTarget] = field(default_factory=list)


@dataclass
class AppConfig:
    tiktok_username: str
    osc_host: str
    osc_port: int
    reconnect_initial_delay: float
    reconnect_max_delay: float
    reconnect_backoff_multiplier: float
    gifts: dict[str, GiftRule]
    warnings: list[str] = field(default_factory=list)


def _cast_value(gift_name: str, value_type: str, raw_value: Any) -> Any:
    if value_type == "int":
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise ConfigError(
                f"Presente '{gift_name}': valor '{raw_value}' não é um inteiro válido "
                f"(type: int)."
            )

    if value_type == "float":
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            raise ConfigError(
                f"Presente '{gift_name}': valor '{raw_value}' não é um float válido "
                f"(type: float)."
            )

    if value_type == "bool":
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return bool(raw_value)
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in _TRUE_STRINGS:
                return True
            if normalized in _FALSE_STRINGS:
                return False
        raise ConfigError(
            f"Presente '{gift_name}': valor '{raw_value}' não pôde ser interpretado "
            f"como bool (use true/false)."
        )

    if value_type == "string":
        return str(raw_value)

    raise ConfigError(
        f"Presente '{gift_name}': tipo '{value_type}' inválido. "
        f"Use um de: {', '.join(VALID_TYPES)}."
    )


def _resolve_address(gift_name: str, item: dict[str, Any]) -> str:
    """
    Resolve o endereço OSC final de um alvo.

    - Se `address` for informado, ele é usado exatamente como está
      (permite mandar para QUALQUER endereço OSC, não só parâmetros
      de avatar — útil se algum dia quiser controlar outra coisa).
    - Caso contrário, `parameter` é obrigatório e o endereço vira
      "/avatar/parameters/<parameter>", que é o padrão do VRChat.
    """
    if "address" in item and item["address"]:
        address = str(item["address"])
        if not address.startswith("/"):
            raise ConfigError(
                f"Presente '{gift_name}': 'address' deve começar com '/' "
                f"(recebido: '{address}')."
            )
        return address

    if "parameter" in item and item["parameter"]:
        return f"{AVATAR_PARAM_PREFIX}{item['parameter']}"

    raise ConfigError(
        f"Presente '{gift_name}': cada alvo precisa de 'parameter' "
        f"(nome do parâmetro do avatar) ou 'address' (endereço OSC completo)."
    )


def _parse_target(gift_name: str, item: dict[str, Any], warnings: list[str]) -> OscTarget:
    if "value" not in item:
        raise ConfigError(f"Presente '{gift_name}': alvo sem 'value' definido.")

    value_type = str(item.get("type", "")).strip().lower()
    if not value_type:
        raise ConfigError(
            f"Presente '{gift_name}': campo 'type' é obrigatório para cada alvo "
            f"(use: {', '.join(VALID_TYPES)}). O VRChat trabalha com Int, Float "
            f"e Bool nos parâmetros de avatar — 'string' também é aceito aqui "
            f"para quem quiser rotear o OSC para outro programa."
        )
    if value_type not in VALID_TYPES:
        raise ConfigError(
            f"Presente '{gift_name}': type '{value_type}' inválido. "
            f"Use um de: {', '.join(VALID_TYPES)}."
        )

    address = _resolve_address(gift_name, item)
    value = _cast_value(gift_name, value_type, item["value"])

    if value_type == "string" and address.startswith(AVATAR_PARAM_PREFIX):
        warnings.append(
            f"Presente '{gift_name}': o parâmetro '{address}' está configurado "
            f"como 'string', mas o VRChat só reconhece parâmetros de avatar "
            f"Int/Float/Bool. Esse valor provavelmente será ignorado pelo "
            f"Animator do avatar (use string apenas se o destino for outro "
            f"programa OSC, não um parâmetro de avatar)."
        )

    return OscTarget(address=address, value_type=value_type, value=value)


def _parse_gift_entry(gift_name: str, raw: dict[str, Any], warnings: list[str]) -> GiftRule:
    targets: list[OscTarget] = []

    if "parameters" in raw:
        # Formato de múltiplos alvos por presente
        for item in raw["parameters"]:
            targets.append(_parse_target(gift_name, item, warnings))
    elif "parameter" in raw or "address" in raw:
        # Formato simples (um único alvo por presente)
        targets.append(_parse_target(gift_name, raw, warnings))
    else:
        raise ConfigError(
            f"Presente '{gift_name}' malformado: defina 'parameter' (ou 'address') "
            f"+ 'type' + 'value', ou uma lista 'parameters' com esses mesmos campos."
        )

    return GiftRule(gift_name=gift_name, targets=targets)


def parse_gift_rule(gift_name: str, raw: dict[str, Any]) -> tuple[GiftRule, list[str]]:
    """
    API pública para validar/converter UM presente isoladamente, a partir
    de um dicionário no mesmo formato usado em config.yaml (com 'parameter'
    ou 'address', 'type' e 'value', ou uma lista 'parameters').

    Usado pela GUI para validar o formulário de um presente e para o botão
    "Testar", sem precisar tocar no config.yaml inteiro.

    Levanta ConfigError se algo estiver inválido. Retorna (GiftRule, warnings).
    """
    warnings: list[str] = []
    rule = _parse_gift_entry(gift_name, raw, warnings)
    return rule, warnings


def load_config(path: str = "config.yaml") -> AppConfig:
    if not os.path.isfile(path):
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        tiktok_username = raw["tiktok"]["username"].lstrip("@")
    except (KeyError, TypeError):
        raise ConfigError("Seção 'tiktok.username' ausente no config.yaml")

    vrchat_raw = raw.get("vrchat", {})
    osc_host = vrchat_raw.get("osc_host", "127.0.0.1")
    osc_port = int(vrchat_raw.get("osc_port", 9000))

    reconnect_raw = raw.get("reconnect", {})
    reconnect_initial_delay = float(reconnect_raw.get("initial_delay", 5))
    reconnect_max_delay = float(reconnect_raw.get("max_delay", 60))
    reconnect_backoff_multiplier = float(reconnect_raw.get("backoff_multiplier", 2))

    gifts_raw = raw.get("gifts", {})
    if not gifts_raw:
        raise ConfigError(
            "Nenhum presente configurado em 'gifts'. Adicione ao menos um "
            "mapeamento presente -> parâmetro OSC no config.yaml."
        )

    warnings: list[str] = []
    gifts: dict[str, GiftRule] = {}
    for gift_name, gift_body in gifts_raw.items():
        gifts[gift_name] = _parse_gift_entry(gift_name, gift_body, warnings)

    return AppConfig(
        tiktok_username=tiktok_username,
        osc_host=osc_host,
        osc_port=osc_port,
        reconnect_initial_delay=reconnect_initial_delay,
        reconnect_max_delay=reconnect_max_delay,
        reconnect_backoff_multiplier=reconnect_backoff_multiplier,
        gifts=gifts,
        warnings=warnings,
    )


def load_raw(path: str = "config.yaml") -> dict[str, Any]:
    """
    Carrega o config.yaml como dicionário "cru" (mesma estrutura do arquivo),
    sem validar nem converter tipos. Usado pela GUI para editar presentes
    preservando exatamente a forma como cada um foi escrito (parameter vs
    address, etc.) antes de salvar de volta.
    """
    if not os.path.isfile(path):
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_raw(path: str, raw: dict[str, Any]) -> None:
    """
    Salva o dicionário "cru" de volta em config.yaml e imediatamente
    revalida o resultado chamando load_config() no arquivo escrito.

    Se a validação falhar, o arquivo NÃO é deixado num estado quebrado:
    a escrita já aconteceu (é a forma mais simples de garantir que o
    round-trip do YAML fica idêntico ao que será lido depois), então em
    caso de erro a exceção é repassada para a GUI mostrar ao usuário —
    normalmente isso só acontece se um valor foi editado manualmente por
    fora da GUI com um erro de digitação.

    Nota: como usamos PyYAML puro, comentários existentes no config.yaml
    são perdidos ao salvar pela GUI. Isso é avisado ao usuário na própria
    interface antes do primeiro save.
    """
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)

    # Revalida lendo de volta o que acabou de ser escrito
    load_config(path)
