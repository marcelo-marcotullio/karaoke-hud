import sounddevice as sd
import soundfile as sf

DURATION = 5        # segundos de gravação
SAMPLE_RATE = 44100  # taxa de amostragem (padrão de CD)

print(f"Gravando {DURATION} segundos...")
audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
sd.wait()  # bloqueia até a gravação terminar
sf.write("sample.wav", audio, SAMPLE_RATE)
print("Salvo em sample.wav")
