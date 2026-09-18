"""
config/loader.py

Responsavel por carregar e validar o arquivo config.yaml.
Nenhum outro modulo deve ler o YAML diretamente -- tudo passa por aqui,
assim adicionar/alterar presentes nunca exige tocar em codigo Python.

CONCEITOS:

- OscTarget: um unico comando OSC (endereco + tipo + valor). Ex: liga o
  parametro "Calcinha" (bool) para true.

- Outfit (conjunto de roupa): uma lista NOMEADA e REUTILIZAVEL de
  OscTarget, definida uma vez em `outfits:` e referenciada por nome em
  varios presentes (e no revert padrao), em vez de repetir a mesma
  lista de pecas em cada presente. Um avatar troca de roupa por PECA
  (calcinha, sutia, camisa, calca, acessorios...), entao um "conjunto"
  normalmente e varias OscTarget juntas.

- GiftRule: o que um presente do TikTok faz. Seus alvos vem da
  combinacao de: um `outfit` (conjunto pre-criado, opcional) + alvos
  extras ad-hoc (`parameter`/`address`/`parameters`, opcional) -- os
  dois podem ser usados juntos (ex: veste o "Conjunto1" e ainda liga
  um efeito extra).

- Duracao + fila: um presente pode ter `duration_minutes` (ou
  `duration_seconds`). Presentes com duracao entram numa fila
  exclusiva (handlers/timed_queue.py): so um fica ativo por vez, e ao
  acabar o tempo o programa manda os alvos de revert (do proprio
  presente -- `revert`/`revert_outfit` -- ou, se nao definidos, o
  padrao global `vrchat.default_revert`/`vrchat.default_revert_outfit`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_TYPES = ("int", "float", "bool", "string")

# Endereco padrao para parametros de avatar do VRChat
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
    # None = presente instantâneo, sem fila (dispara e pronto).
    # Um número = presente "exclusivo": entra na fila, fica ativo por
    # esse tempo (segundos), depois reverte.
    duration_seconds: float | None = None
    # Alvos para onde reverter quando a duração acabar. Se vazio, usa
    # AppConfig.default_revert.
    revert_targets: list[OscTarget] = field(default_factory=list)
    # Nomes dos conjuntos usados (só para exibição na GUI — os alvos já
    # resolvidos estão em `targets`/`revert_targets` acima).
    outfit_name: str | None = None
    revert_outfit_name: str | None = None

    def effective_revert_targets(self, default_revert: list[OscTarget]) -> list[OscTarget]:
        return self.revert_targets or default_revert


@dataclass
class AppConfig:
    tiktok_username: str
    osc_host: str
    osc_port: int
    reconnect_initial_delay: float
    reconnect_max_delay: float
    reconnect_backoff_multiplier: float
    gifts: dict[str, GiftRule]
    outfits: dict[str, list[OscTarget]] = field(default_factory=dict)
    default_revert: list[OscTarget] = field(default_factory=list)
    default_revert_outfit_name: str | None = None
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


def _parse_target_list(label: str, items: list[dict[str, Any]], warnings: list[str]) -> list[OscTarget]:
    return [_parse_target(label, item, warnings) for item in items]


def _parse_outfits(raw: dict[str, Any], warnings: list[str]) -> dict[str, list[OscTarget]]:
    outfits_raw = raw.get("outfits") or {}
    outfits: dict[str, list[OscTarget]] = {}
    for outfit_name, items in outfits_raw.items():
        if not isinstance(items, list) or not items:
            raise ConfigError(
                f"Conjunto de roupa '{outfit_name}' precisa ser uma lista de alvos "
                f"(cada um com 'parameter' ou 'address' + 'type' + 'value')."
            )
        outfits[outfit_name] = _parse_target_list(f"outfit '{outfit_name}'", items, warnings)
    return outfits


def _parse_duration_seconds(gift_name: str, raw: dict[str, Any]) -> float | None:
    has_seconds = "duration_seconds" in raw and raw["duration_seconds"] is not None
    has_minutes = "duration_minutes" in raw and raw["duration_minutes"] is not None

    if has_seconds and has_minutes:
        raise ConfigError(
            f"Presente '{gift_name}': defina 'duration_seconds' OU "
            f"'duration_minutes', não os dois."
        )

    if has_seconds:
        try:
            value = float(raw["duration_seconds"])
        except (TypeError, ValueError):
            raise ConfigError(
                f"Presente '{gift_name}': 'duration_seconds' precisa ser um número."
            )
    elif has_minutes:
        try:
            value = float(raw["duration_minutes"]) * 60.0
        except (TypeError, ValueError):
            raise ConfigError(
                f"Presente '{gift_name}': 'duration_minutes' precisa ser um número."
            )
    else:
        return None

    if value <= 0:
        raise ConfigError(
            f"Presente '{gift_name}': a duração precisa ser maior que zero."
        )
    return value


def _resolve_outfit_targets(
    gift_name: str, outfit_name: str, outfits: dict[str, list[OscTarget]], field_label: str
) -> list[OscTarget]:
    if outfit_name not in outfits:
        raise ConfigError(
            f"Presente '{gift_name}' usa '{field_label}: {outfit_name}', mas esse "
            f"conjunto não existe em 'outfits'. Conjuntos disponíveis: "
            f"{', '.join(sorted(outfits)) or '(nenhum definido)'}."
        )
    return list(outfits[outfit_name])


def _parse_gift_entry(
    gift_name: str,
    raw: dict[str, Any],
    warnings: list[str],
    outfits: dict[str, list[OscTarget]],
) -> GiftRule:
    targets: list[OscTarget] = []
    outfit_name = raw.get("outfit")

    if outfit_name:
        targets.extend(_resolve_outfit_targets(gift_name, outfit_name, outfits, "outfit"))

    if "parameters" in raw:
        for item in raw["parameters"]:
            targets.append(_parse_target(gift_name, item, warnings))
    elif "parameter" in raw or "address" in raw:
        targets.append(_parse_target(gift_name, raw, warnings))

    if not targets:
        raise ConfigError(
            f"Presente '{gift_name}' malformado: defina 'outfit' (conjunto "
            f"pré-criado em 'outfits'), 'parameter'/'address' (um alvo), ou "
            f"'parameters' (lista de alvos) — pode combinar 'outfit' com "
            f"alvos extras se quiser."
        )

    duration_seconds = _parse_duration_seconds(gift_name, raw)

    revert_targets: list[OscTarget] = []
    revert_outfit_name = raw.get("revert_outfit")
    if revert_outfit_name:
        revert_targets.extend(
            _resolve_outfit_targets(gift_name, revert_outfit_name, outfits, "revert_outfit")
        )
    if "revert" in raw and raw["revert"]:
        for item in raw["revert"]:
            revert_targets.append(_parse_target(f"{gift_name} (revert)", item, warnings))

    if revert_targets and duration_seconds is None:
        warnings.append(
            f"Presente '{gift_name}' define revert ('revert'/'revert_outfit') mas "
            f"não tem duração ('duration_minutes'/'duration_seconds') — o revert "
            f"nunca será usado."
        )

    return GiftRule(
        gift_name=gift_name,
        targets=targets,
        duration_seconds=duration_seconds,
        revert_targets=revert_targets,
        outfit_name=outfit_name,
        revert_outfit_name=revert_outfit_name,
    )


def parse_gift_rule(
    gift_name: str, raw: dict[str, Any], outfits: dict[str, list[OscTarget]] | None = None
) -> tuple[GiftRule, list[str]]:
    """
    API pública para validar/converter UM presente isoladamente, a partir
    de um dicionário no mesmo formato usado em config.yaml ('outfit',
    'parameter'/'address', 'type'/'value', 'parameters', 'duration_minutes'/
    'duration_seconds', 'revert'/'revert_outfit').

    Usado pela GUI para validar o formulário de um presente e para o botão
    "Testar", sem precisar tocar no config.yaml inteiro.

    Levanta ConfigError se algo estiver inválido. Retorna (GiftRule, warnings).
    """
    warnings: list[str] = []
    rule = _parse_gift_entry(gift_name, raw, warnings, outfits or {})
    return rule, warnings


def cast_value(value_type: str, raw_value: Any, label: str = "valor") -> Any:
    """
    API pública: converte `raw_value` (normalmente uma string vinda de um
    campo de texto da GUI) para o tipo Python correspondente a `value_type`
    ("int"/"float"/"bool"/"string"), com a mesma validação usada ao
    carregar o config.yaml. Usado ao SALVAR pela GUI, para o YAML gravado
    guardar o tipo certo (`value: 0`, não `value: '0'`).
    """
    return _cast_value(label, value_type, raw_value)


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

    warnings: list[str] = []

    outfits = _parse_outfits(raw, warnings)

    default_revert: list[OscTarget] = []
    default_revert_outfit_name = vrchat_raw.get("default_revert_outfit")
    if default_revert_outfit_name:
        default_revert = _resolve_outfit_targets(
            "vrchat", default_revert_outfit_name, outfits, "default_revert_outfit"
        )
    elif vrchat_raw.get("default_revert"):
        default_revert = _parse_target_list(
            "vrchat.default_revert", vrchat_raw["default_revert"], warnings
        )

    gifts_raw = raw.get("gifts") or {}

    gifts: dict[str, GiftRule] = {}
    for gift_name, gift_body in gifts_raw.items():
        gifts[gift_name] = _parse_gift_entry(gift_name, gift_body, warnings, outfits)

    # Todos presentes com duração precisa de um jeito de reverter, seja
    # próprio ('revert'/'revert_outfit') ou o global.
    for gift_name, rule in gifts.items():
        if rule.duration_seconds is not None and not rule.revert_targets and not default_revert:
            raise ConfigError(
                f"Presente '{gift_name}' tem duração configurada, mas não há "
                f"revert definido para ele ('revert'/'revert_outfit') nem um "
                f"padrão global configurado ('vrchat.default_revert' ou "
                f"'vrchat.default_revert_outfit'). Defina um dos dois para "
                f"saber para onde o avatar deve voltar quando o tempo acabar."
            )

    return AppConfig(
        tiktok_username=tiktok_username,
        osc_host=osc_host,
        osc_port=osc_port,
        reconnect_initial_delay=reconnect_initial_delay,
        reconnect_max_delay=reconnect_max_delay,
        reconnect_backoff_multiplier=reconnect_backoff_multiplier,
        gifts=gifts,
        outfits=outfits,
        default_revert=default_revert,
        default_revert_outfit_name=default_revert_outfit_name,
        warnings=warnings,
    )


def load_raw(path: str = "config.yaml") -> dict[str, Any]:
    """
    Carrega o config.yaml como dicionário "cru" (mesma estrutura do arquivo),
    sem validar nem converter tipos. Usado pela GUI para editar presentes
    preservando exatamente a forma como cada um foi escrito (parameter vs
    address, outfit vs alvos ad-hoc, etc.) antes de salvar de volta.
    """
    if not os.path.isfile(path):
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_raw(path: str, raw: dict[str, Any]) -> None:
    """
    Salva o dicionário "cru" de volta em config.yaml e imediatamente
    revalida o resultado chamando load_config() no arquivo escrito.

    Nota: como usamos PyYAML puro, comentários existentes no config.yaml
    são perdidos ao salvar pela GUI. Isso é avisado ao usuário na própria
    interface antes do primeiro save.
    """
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)

    # Revalida lendo de volta o que acabou de ser escrito
    load_config(path)
