import time
import numpy as np
import openwakeword
from openwakeword.model import Model
import pyaudio

# Initialize openwakeword with built-in models
oww_model = Model(
    wakeword_models=["hey_jarvis", "alexa"],
    inference_framework="onnx",
)


def listen_for_wake_word() -> bool:
    """Continuously listens for wake-words ('Hey Jarvis', 'Jarvis', 'Alexa','Good morning Jarvis')."""
    CHUNK = 1280
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print("\n💤 JARVIS in standby mode... Listening for wake word...")

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_frame = np.frombuffer(data, dtype=np.int16)

        # Predict wake words
        prediction = oww_model.predict(audio_frame)

        for wake_word, score in prediction.items():
            # Lowered threshold to 0.25 for higher sensitivity to "Jarvis" variations
            if score > 0.25:
                print(
                    f"\n⚡ Wake-word detected! [{wake_word}] Score: {score:.2f}"
                )
                stream.stop_stream()
                stream.close()
                audio.terminate()
                return True

        time.sleep(0.01)