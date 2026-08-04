import asyncio
import datetime
import io
import json
import os
import sys
import threading
import time
import webbrowser

# --- PyAudio Fallback ---
try:
    import pyaudio
except ImportError:
    import pyaudiowpatch as pyaudio

    sys.modules["pyaudio"] = pyaudio

# --- Dependencies ---
import ollama
import psutil
import pyautogui
import pyperclip
import pyttsx3
import requests
import speech_recognition as sr
import webview
from PyQt6.QtCore import QObject, pyqtSignal

# Safely import DDGS across package versions
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# --- Custom Modules ---
from gui import JarvisWebGUI
from hand_tracking import start_hand_tracker
from system_controls import (
    change_volume_relative,
    launch_application,
    lock_computer,
    mute_audio,
    play_youtube_song,
    set_master_volume,
    take_screenshot,
    terminate_application,
)
from wake_word import listen_for_wake_word

# Optional OCR
try:
    import pytesseract

    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# Global Web GUI Handle
web_gui = None


class SignalBridge(QObject):
    status_signal = pyqtSignal(str, str)
    log_signal = pyqtSignal(str)


bridge = SignalBridge()

# ==========================================
# 🧠 LONG-TERM MEMORY SYSTEM
# ==========================================

MEMORY_FILE = "memory.json"


def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_user_memory(key: str, value: str) -> str:
    try:
        memories = load_memory()
        clean_key = key.lower().strip().replace(" ", "_")
        memories[clean_key] = value
        with open(MEMORY_FILE, "w") as f:
            json.dump(memories, f, indent=4)
        return f"Stored in memory: {key} = {value}"
    except Exception as e:
        return f"Failed to save memory: {str(e)}"


def recall_user_memories() -> str:
    memories = load_memory()
    if not memories:
        return "No long-term memories stored yet."
    memory_list = [
        f"- {k.replace('_', ' ').title()}: {v}" for k, v in memories.items()
    ]
    return "Memories:\n" + "\n".join(memory_list)


def build_system_prompt() -> str:
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
        "Do not use markdown, asterisks, or formatting symbols."
        f"{memory_context}"
    )


conversation_history = [{"role": "system", "content": build_system_prompt()}]

# ==========================================
# 🛠️ AGENT TOOL DEFINITIONS
# ==========================================


def fetch_live_weather() -> str:
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
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory().percent
    return f"CPU usage is at {cpu} percent, and RAM usage is at {ram} percent."


def read_copied_code_or_text() -> str:
    text = pyperclip.paste()
    return f"Clipboard text: {text[:1000]}" if text.strip() else "Clipboard empty."


TOOLS = [
    get_live_internet_updates,
    get_system_stats,
    read_copied_code_or_text,
    save_user_memory,
    recall_user_memories,
    set_master_volume,
    change_volume_relative,
    mute_audio,
    launch_application,
    terminate_application,
    play_youtube_song,
    take_screenshot,
    lock_computer,
]

available_funcs = {
    "get_live_internet_updates": get_live_internet_updates,
    "get_system_stats": get_system_stats,
    "read_copied_code_or_text": read_copied_code_or_text,
    "save_user_memory": save_user_memory,
    "recall_user_memories": recall_user_memories,
    "set_master_volume": set_master_volume,
    "change_volume_relative": change_volume_relative,
    "mute_audio": mute_audio,
    "launch_application": launch_application,
    "terminate_application": terminate_application,
    "play_youtube_song": play_youtube_song,
    "take_screenshot": take_screenshot,
    "lock_computer": lock_computer,
}

# ==========================================
# 🔊 SPEECH ENGINE & LISTENERS
# ==========================================


def speak(text: str):
    bridge.status_signal.emit("Speaking...", "#00e676")
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


def greet_user():
    greeting = "Systems online, Mam. How can I assist you?"
    conversation_history.append({"role": "assistant", "content": greeting})
    if web_gui:
        web_gui.update_thinking(
            prompt="System Boot", step="Core initialization complete."
        )
    speak(greeting)


def listen_command() -> str:
    r = sr.Recognizer()
    r.pause_threshold = 1.2
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        bridge.status_signal.emit("Listening for Query...", "#ffc107")
        if web_gui:
            web_gui.update_thinking(
                prompt="[AWAITING VOICE INPUT]",
                step="Microphone active. Please speak your question...",
            )

        r.adjust_for_ambient_noise(source, duration=0.3)

        try:
            audio = r.listen(source, timeout=8.0, phrase_time_limit=12.0)
            bridge.status_signal.emit("Converting Voice to Text...", "#9c27b0")

            if web_gui:
                web_gui.update_thinking(
                    prompt="[PROCESSING AUDIO]",
                    step="Sending audio stream to Speech-to-Text engine...",
                )

            query = r.recognize_google(audio, language="en-US").strip()

            if query and web_gui:
                web_gui.append_log(f"User Spoke: {query}")
                web_gui.update_thinking(
                    prompt=query,
                    step="Voice-to-Text successful! Analyzing prompt intent...",
                )

            return query

        except sr.WaitTimeoutError:
            if web_gui:
                web_gui.update_thinking(
                    prompt="[NO SPEECH DETECTED]",
                    step="Listening timed out waiting for input.",
                )
            return ""
        except sr.UnknownValueError:
            if web_gui:
                web_gui.update_thinking(
                    prompt="[UNRECOGNIZED AUDIO]",
                    step="Could not parse speech clearly.",
                )
            return ""
        except Exception as e:
            bridge.log_signal.emit(f"Audio Capture Error: {e}")
            return ""


# ==========================================
# 🧠 EXECUTION ENGINE
# ==========================================


def execute_command(command: str) -> bool:
    if not command:
        return True

    cmd_lower = command.lower()

    if web_gui:
        web_gui.append_log(f"Executing: {command}")
        web_gui.update_thinking(
            prompt=command,
            step="Parsing command intent & checking neural core...",
        )

    exit_triggers = [
        "shutdown",
        "exit",
        "stop",
        "bye",
        "go to sleep",
        "close yourself",
        "quit",
    ]
    if any(trigger in cmd_lower for trigger in exit_triggers):
        speak("Shutting down core protocols. Have a wonderful day, Mam.")
        return False

    if "weather" in cmd_lower:
        if web_gui:
            web_gui.update_thinking(
                prompt=command,
                step="Fetching local weather data...",
                action="fetch_live_weather()",
            )
        weather_reply = fetch_live_weather()
        conversation_history.append(
            {"role": "assistant", "content": weather_reply}
        )
        speak(weather_reply)
        return True

    conversation_history.append({"role": "user", "content": command})
    try:
        if web_gui:
            web_gui.update_thinking(
                prompt=command,
                step="Querying Llama model for function execution...",
            )

        response = ollama.chat(
            model="llama3.2", messages=conversation_history, tools=TOOLS
        )
        msg = response["message"]

        if msg.get("tool_calls"):
            for tool in msg["tool_calls"]:
                fn_name = tool["function"]["name"]
                fn_args = tool["function"]["arguments"]

                if web_gui:
                    web_gui.update_thinking(
                        prompt=command,
                        step=f"Selected tool '{fn_name}'",
                        action=f"{fn_name}({fn_args})",
                    )

                if fn_name in available_funcs:
                    bridge.log_signal.emit(f"Executing Tool: {fn_name}...")
                    tool_output = available_funcs[fn_name](**fn_args)
                    conversation_history.append(
                        {"role": "tool", "content": str(tool_output)}
                    )

                    second_response = ollama.chat(
                        model="llama3.2", messages=conversation_history
                    )
                    ai_reply = second_response["message"]["content"].replace(
                        "*", ""
                    )
                    conversation_history.append(
                        {"role": "assistant", "content": ai_reply}
                    )
                    speak(ai_reply)
                    return True

        ai_reply = msg["content"].replace("*", "")
        if web_gui:
            web_gui.update_thinking(
                prompt=command, step="Response synthesized. Speaking to user."
            )
        conversation_history.append({"role": "assistant", "content": ai_reply})
        speak(ai_reply)

    except Exception as e:
        speak("I encountered an issue processing that request.")
        bridge.log_signal.emit(f"Agent Error: {e}")

    return True


# ==========================================
# 🚀 MAIN LAUNCHER & MULTI-THREADING
# ==========================================


def run_jarvis_backend():
    time.sleep(2)
    greet_user()

    running = True
    while running:
        try:
            if web_gui:
                web_gui.update_state("Standby - Say 'Hey Jarvis'", "#00f0ff")
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                web_gui.update_system_stats(int(cpu), int(ram))
        except Exception:
            pass

        if listen_for_wake_word():
            speak("At your service, Mam.")

            session_start_time = time.time()
            max_idle_seconds = 30

            while running:
                elapsed = time.time() - session_start_time
                if elapsed >= max_idle_seconds:
                    speak("Returning to standby mode, Mam.")
                    if web_gui:
                        web_gui.update_thinking(
                            prompt="[STANDBY]",
                            step="Session timed out. Listening for wake word.",
                        )
                    break

                command = listen_command()

                if command:
                    session_start_time = time.time()
                    running = execute_command(command)
                else:
                    time.sleep(0.2)


def handle_manual_command(cmd_text: str):
    threading.Thread(target=execute_command, args=(cmd_text,), daemon=True).start()


def main():
    global web_gui
    web_gui = JarvisWebGUI(on_command_received=handle_manual_command)

    def ui_log(msg):
        if web_gui:
            web_gui.append_log(msg)

    def ui_status(text, color):
        if web_gui:
            web_gui.update_state(text, color)

    bridge.log_signal.connect(ui_log)
    bridge.status_signal.connect(ui_status)

    start_hand_tracker(web_gui)

    backend_thread = threading.Thread(target=run_jarvis_backend, daemon=True)
    backend_thread.start()

    webview.start()


if __name__ == "__main__":
    main()