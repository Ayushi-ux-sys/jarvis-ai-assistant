import math
import threading
import time
import cv2
import numpy as np
from system_controls import change_volume_relative

last_gesture_time = 0


def start_hand_tracker(gui_instance):
    """Safe hand tracking for Arc Reactor scaling and Thumbs Up/Down gesture detection."""

    def track():
        global last_gesture_time
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("[Hand Tracking] Webcam unavailable.")
            return

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Skin color range detection
            lower_skin = np.array([0, 25, 60], dtype=np.uint8)
            upper_skin = np.array([20, 170, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)

            contours, _ = cv2.findContours(
                mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            if contours:
                max_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(max_contour)

                # 1. Arc Reactor Scaling (Safely wrapped)
                if area > 4000:
                    scale = max(0.5, min(2.5, area / 22000.0))
                    if gui_instance:
                        try:
                            gui_instance.window.evaluate_js(
                                f"window.updateArcScale({scale:.2f});"
                            )
                        except Exception:
                            # Catch and suppress ObjectDisposedException when window closes
                            pass

                    # 2. Thumbs Up / Down Volume Control
                    bx, by, bw, bh = cv2.boundingRect(max_contour)
                    aspect_ratio = float(bw) / float(bh)

                    current_time = time.time()
                    if current_time - last_gesture_time > 2.2:

                        # Vertical contour check for thumb position
                        if aspect_ratio < 0.65 and area > 10000:
                            M = cv2.moments(max_contour)
                            if M["m00"] != 0:
                                cy = int(M["m01"] / M["m00"])
                                relative_cy = (cy - by) / float(bh)

                                # THUMBS UP
                                if relative_cy < 0.42:
                                    change_volume_relative(10)
                                    try:
                                        if gui_instance:
                                            gui_instance.append_log(
                                                "[GESTURE] Thumbs Up: Volume +10%"
                                            )
                                    except Exception:
                                        pass
                                    last_gesture_time = current_time

                                # THUMBS DOWN
                                elif relative_cy > 0.58:
                                    change_volume_relative(-10)
                                    try:
                                        if gui_instance:
                                            gui_instance.append_log(
                                                "[GESTURE] Thumbs Down: Volume -10%"
                                            )
                                    except Exception:
                                        pass
                                    last_gesture_time = current_time

            time.sleep(0.03)

        cap.release()

    tracker_thread = threading.Thread(target=track, daemon=True)
    tracker_thread.start()