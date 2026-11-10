import threading
import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf

DURATION = 12  # janela que o Shazam reconhece; 15s ou mais volta sem match
SAMPLE_RATE = 44100


def input_devices() -> list[tuple[int, str]]:
    """Dispositivos com canal de entrada: (índice, nome)."""
    found: list[tuple[int, str]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device["max_input_channels"]) > 0:
            found.append((index, str(device["name"])))
    return found


def resolve_input(name: str | None) -> int | None:
    """Índice do microfone salvo. None usa o dispositivo padrão do sistema."""
    if not name:
        return None
    for index, found in input_devices():
        if found == name:
            return index
    return None


def record_sample(
    path: Path | str = "sample.wav",
    duration: int = DURATION,
    on_second=None,
    device: int | None = None,
) -> float:
    """Grava `duration` segundos.

    `device` é o índice do PortAudio. None usa a entrada padrão. Devolve o
    `time.time()` do instante em que a gravação começou. `on_second` recebe
    quantos segundos ainda faltam, inclusive o valor inicial.
    """
    path = Path(path)
    start = time.time()
    stop = threading.Event()

    def ticks() -> None:
        for left in range(duration, 0, -1):
            if on_second is not None:
                on_second(left)
            if stop.wait(1):
                return

    if on_second is not None:
        threading.Thread(target=ticks, daemon=True).start()

    audio, rate = _record(duration, device)
    stop.set()
    sf.write(path, audio, rate)
    return start


def _record(duration: int, device: int | None):
    kwargs = {"samplerate": SAMPLE_RATE, "channels": 1}
    if device is not None:
        kwargs["device"] = device
    try:
        audio = sd.rec(int(duration * SAMPLE_RATE), **kwargs)
        sd.wait()
        return audio, SAMPLE_RATE
    except sd.PortAudioError:
        if device is None:
            raise
        rate = int(sd.query_devices(device)["default_samplerate"])
        audio = sd.rec(int(duration * rate), samplerate=rate, channels=1, device=device)
        sd.wait()
        return audio, rate


def main() -> None:
    print(f"Gravando {DURATION} segundos...")
    record_sample()
    print("Salvo em sample.wav")


if __name__ == "__main__":
    main()
