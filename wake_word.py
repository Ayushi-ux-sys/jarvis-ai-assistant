import sys
import time

try:
    import numpy as np
    import openwakeword
    from openwakeword.model import Model as OWWModel

    HAS_OWW = True
except ImportError:
    HAS_OWW = False

try:
    import pyaudio
except ImportError:
    import pyaudiowpatch as pyaudio

    sys.modules["pyaudio"] = pyaudio


def listen_for_wake_word() -> bool:
    """Passively listens in the background using local ONNX models."""
    if not HAS_OWW:
        print("⚠️ openwakeword not installed. Falling back to direct listening...")
        return True

    try:
        # Download missing models if not present
        openwakeword.utils.download_models()

        # Load ONNX wake-word model
        oww_model = OWWModel(inference_framework="onnx")

        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1280

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
                # Lower threshold to 0.3 for higher sensitivity
                if score > 0.3:
                    print(
                        f"\n⚡ Wake-word detected! [{wake_word}] Score: {score:.2f}"
                    )
                    stream.stop_stream()
                    stream.close()
                    audio.terminate()
                    return True

            time.sleep(0.01)

    except Exception as e:
        print(f"[Wake-Word Error]: {e}")
        return True