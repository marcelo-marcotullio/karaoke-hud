import asyncio
import sys
from pathlib import Path

from shazamio import Serialize, Shazam

SAMPLE = Path(__file__).with_name("sample.wav")


async def identify(path: Path) -> tuple[str, str, float] | None:
    """Reconhece a faixa e devolve (artista, título, posição em segundos)."""
    async with Shazam(language="pt-BR", endpoint_country="BR") as shazam:
        raw = await shazam.recognize(path)

    parsed = Serialize.full_track(raw)
    if parsed.track is None or not parsed.matches:
        print("Nenhuma música reconhecida.")
        return None

    artist = parsed.track.subtitle
    title = parsed.track.title
    offset = parsed.matches[0].offset
    print(f"{artist} - {title} (posição na música: {offset:.1f}s)")
    return artist, title, offset


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE
    if not path.is_file():
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)
    asyncio.run(identify(path))


if __name__ == "__main__":
    main()
