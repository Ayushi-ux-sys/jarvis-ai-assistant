import math
import threading
import time
import cv2
import numpy as np
import pyautogui
from system_controls import change_volume_relative, mute_audio

# Cooldown timer to prevent gestures from rapidly re-triggering
last_gesture_time = 0
is_muted = False


def start_hand_tracker(gui_instance):
    """Runs continuous gesture detection for HUD scaling, volume adjustment, muting, and media control."""

    def track():
        global last_gesture_time, is_muted
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("[Hand Tracking] Could not open camera.")
            return

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                time.sleep(0.03)
                continue

            # Mirror frame for natural tracking
            frame = cv2.flip(frame, 1)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Skin color segmentation
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)

            contours, _ = cv2.findContours(
                mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            if contours:
                max_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(max_contour)

                if area > 2500:
                    x, y, w, h = cv2.boundingRect(max_contour)
                    aspect_ratio = float(w) / float(h)

                    # 1. Scale 3D Three.js Arc Reactor in real-time
                    scale = max(0.6, min(2.2, area / 22000.0))
                    if gui_instance and gui_instance.is_alive():
                        try:
                            gui_instance.window.evaluate_js(
                                f"window.updateArcScale({scale:.2f});"
                            )
                        except Exception:
                            pass

                    # 2. Check gesture cooldown (1.2 seconds between commands)
                    current_time = time.time()
                    if current_time - last_gesture_time > 1.2:

                        # Gesture A: Closed Fist (Aspect ratio < 0.55 & low area) -> Volume Down
                        if aspect_ratio < 0.55 and area < 8500:
                            change_volume_relative(-10)
                            if gui_instance and gui_instance.is_alive():
                                gui_instance.append_log(
                                    "[GESTURE] Closed Fist: Volume -10%"
                                )
                            last_gesture_time = current_time

                        # Gesture B: Open Palm (Wide bounding box & high area) -> Volume Up
                        elif aspect_ratio > 1.15 and area > 18000:
                            change_volume_relative(10)
                            if gui_instance and gui_instance.is_alive():
                                gui_instance.append_log(
                                    "[GESTURE] Open Palm: Volume +10%"
                                )
                            last_gesture_time = current_time

                        # Gesture C: Tall / Narrow Two-Finger Sign (0.55 <= ratio <= 0.75) -> Toggle Mute
                        elif 0.55 <= aspect_ratio <= 0.75 and 9000 <= area <= 15000:
                            is_muted = not is_muted
                            mute_audio(is_muted)
                            status_str = "Muted" if is_muted else "Unmuted"
                            if gui_instance and gui_instance.is_alive():
                                gui_instance.append_log(
                                    f"[GESTURE] Two-Finger Sign: Audio {status_str}"
                                )
                            last_gesture_time = current_time

            time.sleep(0.03)

        cap.release()

    tracker_thread = threading.Thread(target=track, daemon=True)
    tracker_thread.start()