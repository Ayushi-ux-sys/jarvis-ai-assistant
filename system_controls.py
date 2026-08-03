import os
import subprocess
import time
import webbrowser
import pyautogui
import pywhatkit
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


def set_master_volume(level_percent: int) -> str:
    """Sets the Windows master audio volume (0 to 100)."""
    try:
        level_percent = max(0, min(100, int(level_percent)))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = interface.QueryInterface(IAudioEndpointVolume)

        # Convert 0-100 to scalar (0.0 to 1.0)
        scalar_vol = level_percent / 100.0
        volume.SetMasterVolumeLevelScalar(scalar_vol, None)
        return f"Set volume to {level_percent} percent."
    except Exception as e:
        return f"Failed to adjust volume: {str(e)}"


def mute_audio(mute: bool = True) -> str:
    """Mutes or unmutes system audio."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMute(1 if mute else 0, None)
        status = "muted" if mute else "unmuted"
        return f"System audio {status}."
    except Exception as e:
        return f"Failed to toggle mute: {str(e)}"


def play_youtube_song(song_name: str) -> str:
    """Searches and plays a specific video or song directly on YouTube."""
    try:
        pywhatkit.playonyt(song_name)
        return f"Playing {song_name} on YouTube."
    except Exception:
        webbrowser.open(
            f"https://www.youtube.com/results?search_query={song_name}"
        )
        return f"Opened YouTube search for {song_name}."


def take_screenshot() -> str:
    """Takes a full-screen screenshot and saves it to the Desktop."""
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        filename = f"JARVIS_Screenshot_{int(time.time())}.png"
        filepath = os.path.join(desktop_path, filename)

        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return f"Screenshot saved to your Desktop as {filename}."
    except Exception as e:
        return f"Failed to take screenshot: {str(e)}"


def lock_computer() -> str:
    """Locks the Windows user session instantly."""
    try:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return "Locking workstation."
    except Exception as e:
        return f"Failed to lock PC: {str(e)}"