import threading
import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf

DURATION = 12  # janela que o Shazam reconhece; 15s ou mais volta sem match
SAMPLE_RATE = 44100


def record_sample(path: Path | str = "sample.wav", duration: int = DURATION, on_second=None) -> float:
    """Grava `duration` segundos no dispositivo de entrada padrão.

    Devolve o `time.time()` do instante em que a gravação começou. `on_second`
    recebe quantos segundos ainda faltam, inclusive o valor inicial.
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

    audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()
    stop.set()
    sf.write(path, audio, SAMPLE_RATE)
    return start


def main() -> None:
    print(f"Gravando {DURATION} segundos...")
    record_sample()
    print("Salvo em sample.wav")


if __name__ == "__main__":
    main()
