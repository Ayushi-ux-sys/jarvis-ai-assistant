import asyncio
import datetime
import io
import json
import os
import sys
import time
import webbrowser
from wake_word import listen_for_wake_word

# --- PyAudio / PyAudioWPatch Fallback for Windows ---
try:
    import pyaudio
except ImportError:
    import pyaudiowpatch as pyaudio

    sys.modules["pyaudio"] = pyaudio

# --- Third-Party Dependencies ---
import ollama
import psutil
import pyautogui
import pyperclip
import pyttsx3
import requests
import speech_recognition as sr
from duckduckgo_search import DDGS

# Optional fast OCR library for screen reading
try:
    import pytesseract

    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# Optional local open-source wake-word detection
try:
    import numpy as np
    from openwakeword.model import Model as OWWModel

    HAS_WAKEWORD = True
except ImportError:
    HAS_WAKEWORD = False

# ==========================================
# 🧠 LONG-TERM MEMORY SYSTEM
# ==========================================

MEMORY_FILE = "memory.json"


def load_memory() -> dict:
    """Loads long-term user memories from a local JSON file."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_user_memory(key: str, value: str) -> str:
    """Saves a key fact or preference to long-term memory."""
    try:
        memories = load_memory()
        clean_key = key.lower().strip().replace(" ", "_")
        memories[clean_key] = value
        with open(MEMORY_FILE, "w") as f:
            json.dump(memories, f, indent=4)
        return f"Stored in long-term memory: {key} = {value}"
    except Exception as e:
        return f"Failed to save memory: {str(e)}"


def recall_user_memories() -> str:
    """Recalls all saved memories stored about the user."""
    memories = load_memory()
    if not memories:
        return "No long-term memories stored yet."

    memory_list = [
        f"- {k.replace('_', ' ').title()}: {v}" for k, v in memories.items()
    ]
    return "Here is what I remember about you:\n" + "\n".join(memory_list)


def build_system_prompt() -> str:
    """Constructs the base system prompt with long-term memory injected."""
    memories = load_memory()
    memory_context = ""
    if memories:
        memory_context = (
            "\n\nSaved User Information & Long-Term Memory:\n"
            + "\n".join(
                [f"- {k.replace('_', ' ')}: {v}" for k, v in memories.items()]
            )
        )

    return (
        "You are JARVIS, an advanced AI assistant. "
        "When answering queries, be direct, polite, and reply in 1-2 concise, spoken conversational sentences. "
        "Do not use markdown, asterisks, formatting symbols, or print raw JSON tool structures."
        f"{memory_context}"
    )


conversation_history = [{"role": "system", "content": build_system_prompt()}]

# ==========================================
# 🛠️ AGENT TOOL DEFINITIONS (MUST BE FIRST)
# ==========================================


def fetch_live_weather() -> str:
    """Fetches real-time weather dynamically based on current IP location."""
    try:
        ip_data = requests.get("https://ipapi.co/json/", timeout=3).json()
        city = ip_data.get("city")

        if city:
            res = requests.get(
                f"https://wttr.in/{city}?format=%C+%t", timeout=3
            )
            if res.status_code == 200:
                return f"The weather in {city} is currently {res.text.strip()}."

        res = requests.get("https://wttr.in/?format=%C+%t", timeout=3)
        if res.status_code == 200:
            return f"The current local weather is {res.text.strip()}."

        return "Unable to retrieve current weather data right now."
    except Exception as e:
        return f"Weather lookup error: {str(e)}"


def get_live_internet_updates(query: str) -> str:
    """Fetches real-time news, sports scores, or live internet data."""
    try:
        if "weather" in query.lower():
            return fetch_live_weather()

        print(f"🌐 Searching web for: {query}...")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results:
                snippets = [f"- {r.get('body', '')}" for r in results]
                return "\n".join(snippets)
            return "No real-time web results found for this request."

    except Exception as e:
        return f"Live lookup error: {str(e)}"


def get_system_stats() -> str:
    """Returns current CPU and RAM usage percentages."""
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory().percent
    return f"CPU usage is at {cpu} percent, and RAM usage is at {ram} percent."


def close_application(app_name: str) -> str:
    """Safely closes a running Windows application by process name."""
    app_clean = app_name.lower().strip()

    if "code" in app_clean or "jarvis" in app_clean:
        return "I will not close your active development editor, Mam."

    executable_map = {
        "chrome": "chrome.exe",
        "browser": "chrome.exe",
        "notepad": "notepad.exe",
        "spotify": "Spotify.exe",
    }

    target_exe = executable_map.get(app_clean, f"{app_clean}.exe")
    closed_any = False

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (
                proc.info["name"]
                and proc.info["name"].lower() == target_exe.lower()
            ):
                proc.terminate()
                closed_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if closed_any:
        return f"Closed {app_name}."
    else:
        return f"Could not find {app_name} running."


def read_copied_code_or_text() -> str:
    """Reads whatever text or code is copied to the clipboard."""
    text = pyperclip.paste()
    if text and len(text.strip()) > 0:
        return f"Clipboard text: {text[:1000]}"
    return "Clipboard is empty."


def capture_screen_and_describe(
    prompt: str = "Summarize screen briefly",
) -> str:
    """Explicit tool to extract screen text via OCR."""
    try:
        screenshot = pyautogui.screenshot()

        if HAS_OCR:
            screen_text = pytesseract.image_to_string(screenshot)
            if screen_text.strip():
                response = ollama.chat(
                    model="llama3.2",
                    messages=[
                        {
                            "role": "user",
                            "content": f"{prompt}. Screen text:\n\n{screen_text[:1000]}",
                        }
                    ],
                )
                return response["message"]["content"]

        clipboard_text = pyperclip.paste()
        if clipboard_text.strip():
            return f"Screen text unreadable, clipboard content: {clipboard_text[:300]}"

        return "Could not extract readable screen text."

    except Exception as e:
        return f"Screen analysis error: {str(e)}"


def open_application_or_site(target: str) -> str:
    """Opens a website or application on the computer."""
    target_clean = target.lower().strip()
    if "youtube" in target_clean:
        webbrowser.open("https://www.youtube.com")
        return "Opened YouTube."
    elif "google" in target_clean:
        webbrowser.open("https://www.google.com")
        return "Opened Google."
    elif "github" in target_clean:
        webbrowser.open("https://www.github.com")
        return "Opened GitHub."
    else:
        webbrowser.open(f"https://www.google.com/search?q={target}")
        return f"Searching Google for {target}."


# ==========================================
# ⚙️ AGENT TOOLS REGISTRATION
# ==========================================

TOOLS = [
    get_live_internet_updates,
    get_system_stats,
    close_application,
    read_copied_code_or_text,
    open_application_or_site,
    save_user_memory,
    recall_user_memories,
]

available_funcs = {
    "get_live_internet_updates": get_live_internet_updates,
    "get_system_stats": get_system_stats,
    "close_application": close_application,
    "read_copied_code_or_text": read_copied_code_or_text,
    "open_application_or_site": open_application_or_site,
    "save_user_memory": save_user_memory,
    "recall_user_memories": recall_user_memories,
}

# ==========================================
# 🔊 SPEECH ENGINE & LISTENERS
# ==========================================


def speak(text: str):
    """Prints text and speaks out loud."""
    print(f"\n🤖 JARVIS: {text}")
    try:
        tts_engine = pyttsx3.init("sapi5")
        tts_engine.setProperty("rate", 185)

        voices = tts_engine.getProperty("voices")
        if len(voices) > 0:
            tts_engine.setProperty("voice", voices[0].id)

        tts_engine.say(text)
        tts_engine.runAndWait()
        tts_engine.stop()
    except Exception as e:
        print(f"[Speech Error]: {e}")


def greet_user():
    greeting = "Systems online, Mam. How can I assist you?"
    conversation_history.append({"role": "assistant", "content": greeting})
    speak(greeting)


def listen_command() -> str:
    """Listens dynamically without hard timeouts until the user stops speaking."""
    r = sr.Recognizer()
    r.pause_threshold = 2.0
    r.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        print("\n🎤 Listening (take your time)...")
        r.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = r.listen(source, timeout=None, phrase_time_limit=None)
            print("🧠 Processing...")
            query = r.recognize_google(audio, language="en-US")
            print(f"👤 MAM: {query}")
            return query.strip()
        except Exception:
            return ""


def wait_for_wakeword() -> bool:
    """Passively listens in the background for a wake-word if openwakeword is installed."""
    if not HAS_WAKEWORD:
        return True  # Fallback: directly proceed to active microphone listening

    try:
        oww_model = OWWModel()
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

        print("\n💤 JARVIS in standby mode. Say 'Hey Jarvis'...")

        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_frame = np.frombuffer(data, dtype=np.int16)

            prediction = oww_model.predict(audio_frame)

            for wake_word, score in prediction.items():
                if score > 0.5:
                    print(f"⚡ Wake-word detected ({wake_word})!")
                    speak("At your service.")
                    stream.stop_stream()
                    stream.close()
                    audio.terminate()
                    return True

    except Exception as e:
        print(f"[Wake-word Error]: {e}")
        return True


# ==========================================
# 🧠 EXECUTION ENGINE
# ==========================================


def execute_command(command: str) -> bool:
    if not command:
        return True

    cmd_lower = command.lower()

    # 1. Immediate System Exit Triggers
    exit_triggers = [
        "shutdown",
        "exit",
        "stop",
        "bye",
        "go to sleep",
        "close yourself",
        "exit jar",
        "quit",
        "terminate",
    ]
    if any(trigger in cmd_lower for trigger in exit_triggers):
        speak("Shutting down core protocols. Have a wonderful day, Mam.")
        time.sleep(0.5)
        return False

    # 2. Weather Direct Shortcut
    if "weather" in cmd_lower:
        weather_reply = fetch_live_weather()
        conversation_history.append(
            {"role": "assistant", "content": weather_reply}
        )
        speak(weather_reply)
        return True

    # 3. Explicit Screen Inspection
    screen_keywords = ["screen", "look at", "read monitor", "what do you see"]
    if any(kw in cmd_lower for kw in screen_keywords):
        print("📺 Analyzing screen...")
        screen_summary = capture_screen_and_describe(command)
        clean_summary = (
            screen_summary.replace("*", "").replace("#", "").replace("`", "")
        )
        speak(clean_summary)
        return True

    # 4. Ollama Dynamic Processing
    conversation_history.append({"role": "user", "content": command})

    try:
        response = ollama.chat(
            model="llama3.2",
            messages=conversation_history,
            tools=TOOLS,
        )

        msg = response["message"]

        # Handle Native Tool Call
        if msg.get("tool_calls"):
            for tool in msg["tool_calls"]:
                fn_name = tool["function"]["name"]
                fn_args = tool["function"]["arguments"]

                if fn_name in available_funcs:
                    print(f"⚙️ Executing Tool: {fn_name}...")
                    tool_output = available_funcs[fn_name](**fn_args)
                    conversation_history.append(
                        {"role": "tool", "content": str(tool_output)}
                    )

                    second_response = ollama.chat(
                        model="llama3.2", messages=conversation_history
                    )
                    ai_reply = second_response["message"]["content"]
                    clean_reply = (
                        ai_reply.replace("*", "")
                        .replace("#", "")
                        .replace("`", "")
                    )
                    conversation_history.append(
                        {"role": "assistant", "content": clean_reply}
                    )
                    speak(clean_reply)
                    return True

        # Handle Raw JSON Fallback
        raw_content = msg.get("content", "").strip()
        if raw_content.startswith("{") and "name" in raw_content:
            try:
                parsed_tool = json.loads(raw_content)
                fn_name = parsed_tool.get("name")
                fn_args = parsed_tool.get("parameters", {})

                if fn_name in available_funcs:
                    print(f"⚙️ Executing Tool (JSON Fallback): {fn_name}...")
                    tool_output = available_funcs[fn_name](**fn_args)
                    conversation_history.append(
                        {"role": "tool", "content": str(tool_output)}
                    )

                    second_response = ollama.chat(
                        model="llama3.2", messages=conversation_history
                    )
                    ai_reply = second_response["message"]["content"]
                    clean_reply = (
                        ai_reply.replace("*", "")
                        .replace("#", "")
                        .replace("`", "")
                    )
                    conversation_history.append(
                        {"role": "assistant", "content": clean_reply}
                    )
                    speak(clean_reply)
                    return True
            except Exception:
                pass

        # Standard Speech Answer
        ai_reply = msg["content"]
        clean_reply = (
            ai_reply.replace("*", "").replace("#", "").replace("`", "")
        )
        conversation_history.append(
            {"role": "assistant", "content": clean_reply}
        )
        speak(clean_reply)

    except Exception as e:
        speak("I encountered an issue with my local neural core.")
        print(f"[Agent Error]: {e}")

    return True


def main():
    print("Initializing JARVIS AI Agent Systems...")
    greet_user()

    running = True
    while running:
        # Wait in passive mode until wake-word is heard
        if listen_for_wake_word():
            speak("At your service, Mam.")

            command = listen_command()
            if command:
                running = execute_command(command)

if __name__ == "__main__":
    main()