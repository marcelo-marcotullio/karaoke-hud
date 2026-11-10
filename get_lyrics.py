import re
import sys

import requests

USER_AGENT = "karaoke-hud v0.1"
SEARCH_URL = "https://lrclib.net/api/search"
LRC_LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def parse_lrc(lrc_text: str) -> list[tuple[float, str]]:
    lines: list[tuple[float, str]] = []
    for line in lrc_text.strip().splitlines():
        match = LRC_LINE.match(line.strip())
        if not match:
            continue
        timestamp = int(match.group(1)) * 60 + float(match.group(2))
        lines.append((timestamp, match.group(3).strip()))
    return sorted(lines)


def lines_around(lines: list[tuple[float, str]], position: float) -> tuple[str, str, str]:
    """Devolve (anterior, atual, próxima) para a posição da música, em segundos."""
    previous = ""
    current = ""
    upcoming = ""
    for timestamp, text in lines:
        if timestamp <= position:
            if text:
                previous = current
                current = text
            continue
        if text:
            upcoming = text
            break
    if not current:
        return "", "", upcoming
    return previous, current, upcoming


def _search(artist: str, title: str) -> list[dict]:
    response = requests.get(
        SEARCH_URL,
        params={"artist_name": artist, "track_name": title},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _simplify(title: str) -> str:
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", title).strip()


def fetch_lyrics(artist: str, title: str) -> dict | None:
    """Busca a letra no LRCLIB.

    Devolve um dict com `synced` (lista de (segundo, texto)), `plain` e
    `instrumental`. None quando não há resultado.
    """
    results = _search(artist, title)
    simplified = _simplify(title)
    if not results and simplified and simplified != title:
        results = _search(artist, simplified)
    if not results:
        return None

    chosen = next((item for item in results if item.get("syncedLyrics")), results[0])
    synced_text = chosen.get("syncedLyrics") or ""
    return {
        "synced": parse_lrc(synced_text) if synced_text else [],
        "plain": (chosen.get("plainLyrics") or "").strip(),
        "instrumental": bool(chosen.get("instrumental")),
    }


def main() -> None:
    artist = sys.argv[1] if len(sys.argv) > 2 else "Arch Enemy"
    title = sys.argv[2] if len(sys.argv) > 2 else "Symphony of Destruction"
    found = fetch_lyrics(artist, title)
    if not found or not found["synced"]:
        print("Letra sincronizada não encontrada.")
        return
    print("\n".join(f"[{timestamp:.2f}] {text}" for timestamp, text in found["synced"]))


if __name__ == "__main__":
    main()
