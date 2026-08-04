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
    """Continuously listens for wake-words ('Hey Jarvis', 'Alexa') and flushes audio state on exit."""
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

    # Flush model internal prediction buffers from previous detections
    oww_model.reset()

    print("\n💤 JARVIS in standby mode... Listening for wake word...")

    detected = False
    while not detected:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_frame = np.frombuffer(data, dtype=np.int16)

            prediction = oww_model.predict(audio_frame)

            for wake_word, score in prediction.items():
                if score > 0.40:  # Threshold to prevent accidental triggers
                    print(
                        f"\n⚡ Wake-word detected! [{wake_word}] Score: {score:.2f}"
                    )
                    detected = True
                    break
        except Exception:
            pass

        time.sleep(0.01)

    # Clean up audio stream & release microphone device for SpeechRecognition
    try:
        stream.stop_stream()
        stream.close()
        audio.terminate()
    except Exception:
        pass

    oww_model.reset()
    time.sleep(0.4)  # Brief delay to allow Windows audio drivers to free the mic
    return True