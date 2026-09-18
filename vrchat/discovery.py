"""
vrchat/discovery.py

Le os arquivos que o PROPRIO VRChat gera automaticamente com a lista de
parametros de cada avatar carregado (com OSC habilitado), para nao
precisar adivinhar nomes de parametro.

Quando voce carrega um avatar no VRChat com OSC ligado, o jogo cria um
arquivo JSON em:

    Windows: %USERPROFILE%\\AppData\\LocalLow\\VRChat\\VRChat\\OSC\\{userId}\\Avatars\\{avatarId}.json

O formato documentado oficialmente e:
    {
      "id": "avtr_...",
      "name": "Nome do avatar",
      "parameters": [
        {
          "name": "NomeDoParametro",
          "input": {"address": "/avatar/parameters/NomeDoParametro", "type": "Bool"},
          "output": {"address": "/avatar/parameters/NomeDoParametro", "type": "Bool"}
        },
        ...
      ]
    }

Mas como o proprio VRChat avisa que esse sistema de arquivo e "provisorio"
e pode mudar, este modulo tenta ser tolerante a variacoes razoaveis dessa
estrutura (lista na raiz em vez de objeto, campos sem "input"/"output"
aninhados, etc.) e SEMPRE relata o que encontrou/o que falhou, em vez de
simplesmente engolir o erro e mostrar "nada encontrado" sem explicar por que.

Este modulo so LE esses arquivos -- nunca escreve neles.
Referencia oficial: https://docs.vrchat.com/docs/osc-avatar-parameters
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field


@dataclass
class DiscoveredParameter:
    name: str
    address: str
    osc_type: str  # "Int" | "Float" | "Bool" (ou "?" se nao identificado)
    writable: bool  # False = parece ser so de leitura (sem secao "input")

    @property
    def loader_type(self) -> str:
        """Tipo no formato usado pelo config.yaml (int/float/bool)."""
        return {"int": "int", "float": "float", "bool": "bool"}.get(
            self.osc_type.strip().lower(), "int"
        )


@dataclass
class DiscoveredAvatar:
    avatar_id: str
    avatar_name: str
    file_path: str
    modified_at: float
    parameters: list[DiscoveredParameter] = field(default_factory=list)

    @property
    def label(self) -> str:
        name = self.avatar_name or "(sem nome)"
        return f"{name}  [{self.avatar_id}]"


@dataclass
class ScanDiagnostics:
    osc_dir: str | None
    json_files_found: int = 0
    avatars_loaded: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)  # (arquivo, motivo)


def default_osc_config_dir() -> str | None:
    """
    Retorna a pasta onde o VRChat guarda os configs de OSC dos avatares.
    So funciona no Windows (onde o VRChat roda nativamente); em outros
    sistemas retorna None.
    """
    userprofile = os.environ.get("USERPROFILE")
    if not userprofile:
        return None
    path = os.path.join(userprofile, "AppData", "LocalLow", "VRChat", "VRChat", "OSC")
    return path if os.path.isdir(path) else None


def _find_avatar_json_files(osc_dir: str) -> list[str]:
    pattern = os.path.join(osc_dir, "*", "Avatars", "*.json")
    return glob.glob(pattern)


def _extract_parameter(item: dict) -> DiscoveredParameter | None:
    """
    Extrai um DiscoveredParameter de UM item da lista de parametros,
    tolerando algumas variacoes de formato conhecidas:

    - Formato documentado: {"name": ..., "input": {"address":..,"type":..},
      "output": {"address":..,"type":..}}
    - Formato "achatado" (sem input/output aninhado): {"name":..,
      "address":.., "type":..}
    - "input" ausente/None (parametro so de leitura) -> usa "output".
    """
    if not isinstance(item, dict):
        return None

    name = item.get("name")
    if not name:
        return None

    input_info = item.get("input")
    output_info = item.get("output")

    if isinstance(input_info, dict) and input_info.get("address"):
        return DiscoveredParameter(
            name=name,
            address=input_info["address"],
            osc_type=str(input_info.get("type", "?")),
            writable=True,
        )

    if isinstance(output_info, dict) and output_info.get("address"):
        return DiscoveredParameter(
            name=name,
            address=output_info["address"],
            osc_type=str(output_info.get("type", "?")),
            writable=False,
        )

    # Formato achatado: sem "input"/"output", campos direto no item
    if item.get("address"):
        return DiscoveredParameter(
            name=name,
            address=str(item["address"]),
            osc_type=str(item.get("type", "?")),
            writable=True,
        )

    # Ultimo recurso: so temos o nome. Ainda assim e util pro usuario --
    # assume o endereco padrao do VRChat pro nome do parametro.
    return DiscoveredParameter(
        name=name,
        address=f"/avatar/parameters/{name}",
        osc_type=str(item.get("type", "?")),
        writable=True,
    )


def _find_parameters_list(data) -> list | None:
    """
    Localiza a lista de parametros dentro do JSON carregado, tolerando
    variações: lista direto na raiz, ou dentro de uma chave "parameters"
    (ou, como último recurso, qualquer chave cujo valor seja uma lista
    de dicts com "name").
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        params = data.get("parameters")
        if isinstance(params, list):
            return params

        # fallback heuristico: procura qualquer lista de dicts com "name"
        for value in data.values():
            if (
                isinstance(value, list)
                and value
                and all(isinstance(v, dict) and "name" in v for v in value)
            ):
                return value

    return None


def parse_avatar_config_file(path: str) -> tuple[DiscoveredAvatar | None, str | None]:
    """
    Le e converte UM arquivo de config de avatar. Retorna
    (DiscoveredAvatar, None) em caso de sucesso, ou (None, motivo) se
    algo deu errado -- nunca levanta exceção, para o chamador poder
    mostrar diagnóstico em vez de simplesmente sumir com o arquivo.
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                data = json.load(f)
        except Exception as exc:  # noqa: BLE001
            return None, f"não consegui decodificar o arquivo: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"JSON inválido: {exc}"
    except OSError as exc:
        return None, f"não consegui abrir o arquivo: {exc}"

    params_raw = _find_parameters_list(data)
    if params_raw is None:
        kind = type(data).__name__
        keys = list(data.keys()) if isinstance(data, dict) else None
        return None, (
            f"não encontrei uma lista de parâmetros reconhecível "
            f"(JSON raiz é {kind}{f', chaves: {keys}' if keys else ''})"
        )

    parameters: list[DiscoveredParameter] = []
    for item in params_raw:
        p = _extract_parameter(item)
        if p is not None:
            parameters.append(p)
    parameters.sort(key=lambda p: p.name.lower())

    if isinstance(data, dict):
        avatar_id = str(data.get("id") or "")
        avatar_name = str(data.get("name") or "")
    else:
        avatar_id = ""
        avatar_name = ""

    filename_stem = os.path.splitext(os.path.basename(path))[0]
    if not avatar_id:
        # o id costuma estar embutido no nome do arquivo (ex: "..._avtr_xxxx")
        avatar_id = filename_stem
    if not avatar_name:
        avatar_name = filename_stem

    try:
        modified_at = os.path.getmtime(path)
    except OSError:
        modified_at = 0.0

    if not parameters:
        return None, "o arquivo abriu, mas não tinha nenhum parâmetro com nome dentro"

    return (
        DiscoveredAvatar(
            avatar_id=avatar_id,
            avatar_name=avatar_name,
            file_path=path,
            modified_at=modified_at,
            parameters=parameters,
        ),
        None,
    )


def find_avatars(osc_dir: str | None = None) -> tuple[list[DiscoveredAvatar], ScanDiagnostics]:
    """
    Procura todos os arquivos de config de avatar que o VRChat ja gerou
    (para qualquer conta local nessa mesma pasta OSC) e retorna, do mais
    recente para o mais antigo, junto com um diagnóstico do que foi
    encontrado/o que falhou (para poder mostrar isso na GUI em vez de só
    "nada encontrado").
    """
    resolved_dir = osc_dir or default_osc_config_dir()
    diagnostics = ScanDiagnostics(osc_dir=resolved_dir)

    if not resolved_dir or not os.path.isdir(resolved_dir):
        return [], diagnostics

    avatars: list[DiscoveredAvatar] = []
    json_paths = _find_avatar_json_files(resolved_dir)
    diagnostics.json_files_found = len(json_paths)

    for path in json_paths:
        avatar, error = parse_avatar_config_file(path)
        if avatar is not None:
            avatars.append(avatar)
        else:
            diagnostics.errors.append((path, error or "motivo desconhecido"))

    diagnostics.avatars_loaded = len(avatars)
    avatars.sort(key=lambda a: a.modified_at, reverse=True)
    return avatars, diagnostics
