import os
import subprocess
import webbrowser
import pyautogui

# Windows Core Audio API imports (compatible with all pycaw versions)
try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    
    # Check for direct Activate support or extract device endpoint
    if hasattr(speakers, 'Activate'):
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    elif hasattr(speakers, 'Endpoint'):
        interface = speakers.Endpoint.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    else:
        interface = speakers._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        
    volume_control = interface.QueryInterface(IAudioEndpointVolume)
    HAS_PYCAW = True
except Exception as e:
    print(f"[Volume API Error]: {e}")
    HAS_PYCAW = False


def set_master_volume(level: int) -> str:
    """Sets master volume to an exact percentage (0-100)."""
    try:
        level = max(0, min(100, int(level)))
        if HAS_PYCAW:
            volume_control.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Master volume set to {level} percent."
        else:
            for _ in range(50):
                pyautogui.press("volumedown")
            for _ in range(level // 2):
                pyautogui.press("volumeup")
            return f"Adjusted volume to roughly {level} percent."
    except Exception as e:
        return f"Failed to set volume: {e}"


def change_volume_relative(delta: int) -> str:
    """Changes master volume up (+) or down (-) by delta percentage."""
    try:
        if HAS_PYCAW:
            current = volume_control.GetMasterVolumeLevelScalar()
            new_level = max(0.0, min(1.0, current + (delta / 100.0)))
            volume_control.SetMasterVolumeLevelScalar(new_level, None)
            return f"Volume adjusted by {delta}%."
        else:
            key = "volumeup" if delta > 0 else "volumedown"
            for _ in range(abs(delta) // 2):
                pyautogui.press(key)
            return f"Volume shifted by {delta}%."
    except Exception as e:
        return f"Failed to change volume: {e}"


def mute_audio(mute: bool = True) -> str:
    try:
        if HAS_PYCAW:
            volume_control.SetMute(1 if mute else 0, None)
            return "Audio muted." if mute else "Audio unmuted."
        else:
            pyautogui.press("volumemute")
            return "Toggled mute."
    except Exception as e:
        return f"Mute error: {e}"


def launch_application(app_name: str) -> str:
    try:
        os.system(f"start {app_name}")
        return f"Launched {app_name}."
    except Exception as e:
        return f"Failed to launch app: {e}"


def terminate_application(app_name: str) -> str:
    try:
        os.system(f"taskkill /f /im {app_name}.exe")
        return f"Closed {app_name}."
    except Exception as e:
        return f"Failed to terminate app: {e}"


def play_youtube_song(song_name: str) -> str:
    webbrowser.open(
        f"https://www.youtube.com/results?search_query={song_name}"
    )
    return f"Searching YouTube for {song_name}."


def take_screenshot() -> str:
    try:
        pyautogui.screenshot("screenshot.png")
        return "Screenshot saved as screenshot.png."
    except Exception as e:
        return f"Screenshot failed: {e}"


def lock_computer() -> str:
    os.system("rundll32.exe user32.dll,LockWorkStation")
    return "Locking system."