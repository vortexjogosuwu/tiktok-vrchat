"""
tiktok/catalog.py

Duas fontes de nomes de presente do TikTok, para ajudar a preencher o
formulário sem precisar adivinhar ou digitar errado:

1. fetch_live_gift_catalog(username): busca o catálogo REAL de
   presentes da conta, direto da TikTokLive. É a fonte confiável e
   sempre certa -- mas só funciona enquanto a conta está AO VIVO no
   momento da busca, porque é assim que o TikTok expõe essa lista.

2. COMMON_GIFT_SUGGESTIONS: uma lista de nomes de presentes comuns/
   populares do TikTok, para consulta offline quando a conta não
   estiver ao vivo. NÃO é uma lista oficial, pode variar por região e
   pode ficar desatualizada -- é só um ponto de partida para digitar
   menos errado. Sempre que possível, prefira a busca da LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GiftInfo:
    name: str
    diamond_count: int | None = None


async def fetch_live_gift_catalog(username: str) -> list[GiftInfo]:
    """
    Busca a lista de presentes disponíveis para o canal, usando a API
    que o TikTok expõe para contas atualmente AO VIVO.

    Levanta RuntimeError com uma mensagem amigável se a conta não
    estiver ao vivo ou se algo mais falhar. Não deixa nenhuma conexão
    aberta ao terminar.
    """
    from TikTokLive import TikTokLiveClient

    username = username.lstrip("@").strip()
    if not username:
        raise RuntimeError("Informe o @ do canal do TikTok primeiro.")

    client = TikTokLiveClient(unique_id=f"@{username}")

    try:
        is_live = await client.is_live()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Não foi possível verificar se @{username} está ao vivo: {exc}"
        ) from None

    if not is_live:
        raise RuntimeError(
            f"@{username} não está ao vivo agora. A lista de presentes só pode "
            f"ser buscada direto do TikTok enquanto a conta está transmitindo "
            f"(é assim que o TikTok disponibiliza essa informação). Tente de "
            f"novo durante uma LIVE, ou use a lista de sugestões abaixo."
        )

    try:
        await client.retrieve_room_info()
        await client.retrieve_available_gifts()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao buscar a lista de presentes: {exc}") from None
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    gifts_raw = getattr(client, "available_gifts", None) or {}
    results: list[GiftInfo] = []
    for gift in gifts_raw.values():
        name = getattr(gift, "name", None)
        if not name:
            info = getattr(gift, "info", None)
            name = getattr(info, "name", None) if info else None
        if not name:
            continue
        diamond_count = getattr(gift, "diamond_count", None)
        results.append(GiftInfo(name=name, diamond_count=diamond_count))

    if not results:
        raise RuntimeError(
            "A conta está ao vivo, mas não recebi nenhum presente na resposta "
            "do TikTok. Tente novamente em alguns segundos."
        )

    results.sort(key=lambda g: g.name.lower())
    return results


# Lista de sugestões comuns, para quando a conta não está ao vivo.
# Não oficial, pode variar por região/conta e ficar desatualizada.
COMMON_GIFT_SUGGESTIONS: list[str] = sorted([
    "Rose", "TikTok", "GG", "Heart", "Finger Heart", "Hand Hearts",
    "Ice Cream Cone", "Perfume", "Doughnut", "Sunglasses", "Little Crown",
    "Panda", "Confetti", "Star", "Thumbs Up", "Rainbow Puke", "Hi Bear",
    "Cheer For You", "Corgi", "Money Gun", "Drama Queen", "Galaxy",
    "Interstellar", "Meteor Shower", "Lion", "Whale Diving", "Falcon",
    "TikTok Universe", "Sports Car", "Yacht", "Fireworks", "Diamond Ring",
    "Leon the Kitten", "Garland Headpiece", "Gold Mine Cart", "Train",
    "Motorcycle", "Coral", "Adam's Dream", "I'm Very Rich", "Mic",
    "Love You", "Sunset", "Naughty Angel", "Marvelous Confetti",
    "Concert", "Watermelon Love", "Stinky Tofu", "Cap", "Football",
])
