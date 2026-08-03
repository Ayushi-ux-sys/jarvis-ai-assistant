import asyncio
import datetime
import io
import json
import os
import sys
import threading
import time
import webbrowser

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
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

# --- Custom Modules ---
from gui import JarvisHUD
from wake_word import listen_for_wake_word

# Optional fast OCR library for screen reading
try:
    import pytesseract

    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# ==========================================
# 🛰️ THREAD SIGNAL BRIDGE FOR GUI UPDATES
# ==========================================


class SignalBridge(QObject):
    """Bridge to send thread-safe signals from JARVIS agent loop to PyQt GUI."""

    status_signal = pyqtSignal(str, str)  # status_text, color_hex
    log_signal = pyqtSignal(str)


bridge = SignalBridge()

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
# 🛠️ AGENT TOOL DEFINITIONS
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

        bridge.log_signal.emit(f"Searching web for: {query}...")
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
    """Prints text, updates GUI log, and speaks out loud."""
    bridge.status_signal.emit("Speaking...", "#00e676")  # Green Glow
    bridge.log_signal.emit(f"JARVIS: {text}")

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

    bridge.status_signal.emit("System Standby", "#00d2ff")  # Cyan Glow


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
        bridge.status_signal.emit("Listening...", "#ffc107")  # Yellow Glow
        bridge.log_signal.emit("Listening (take your time)...")
        r.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = r.listen(source, timeout=None, phrase_time_limit=None)
            bridge.status_signal.emit("Processing Voice...", "#9c27b0")  # Purple
            query = r.recognize_google(audio, language="en-US")
            bridge.log_signal.emit(f"Mam: {query}")
            return query.strip()
        except Exception:
            return ""


# ==========================================
# 🧠 EXECUTION ENGINE
# ==========================================


def execute_command(command: str) -> bool:
    if not command:
        return True

    cmd_lower = command.lower()

    # 1. System Shutdown Triggers
    exit_triggers = [
        "shutdown",
        "exit",
        "stop",
        "bye",
        "go to sleep",
        "close yourself",
        "exit jarvis",
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
        bridge.log_signal.emit("Analyzing screen...")
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

        # Native Tool Call Handling
        if msg.get("tool_calls"):
            for tool in msg["tool_calls"]:
                fn_name = tool["function"]["name"]
                fn_args = tool["function"]["arguments"]

                if fn_name in available_funcs:
                    bridge.log_signal.emit(f"Executing Tool: {fn_name}...")
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

        # Fallback Standard Speech
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
        bridge.log_signal.emit(f"Agent Error: {e}")

    return True


# ==========================================
# 🚀 MAIN LAUNCHER & MULTI-THREADING
# ==========================================


def run_jarvis_backend():
    """Runs the backend agent loop continuously in a secondary background thread."""
    time.sleep(1)  # Allow GUI to fully initialize
    greet_user()

    running = True
    while running:
        bridge.status_signal.emit(
            "Standby - Say 'Hey Jarvis'", "#00d2ff"
        )  # Cyan
        if listen_for_wake_word():
            speak("At your service, Mam.")
            command = listen_command()
            if command:
                running = execute_command(command)


def main():
    app = QApplication(sys.argv)

    # Initialize PyQt HUD
    gui = JarvisHUD()

    # Connect Signals from Backend Thread to GUI Updates
    bridge.status_signal.connect(gui.update_state)
    bridge.log_signal.connect(gui.append_log)

    # Launch JARVIS Backend Loop in Background Thread
    backend_thread = threading.Thread(target=run_jarvis_backend, daemon=True)
    backend_thread.start()

    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()