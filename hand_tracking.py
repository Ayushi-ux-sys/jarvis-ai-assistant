import math
import threading
import time
import cv2
import numpy as np
from system_controls import change_volume_relative

last_gesture_time = 0


def start_hand_tracker(gui_instance):
    """Tracks hand position (X, Y) and scale to dynamically move and zoom the 3D core."""

    def track():
        global last_gesture_time
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("[Hand Tracking] Webcam unavailable.")
            return

        while cap.isOpened():
            if gui_instance and not gui_instance.is_alive():
                break

            success, frame = cap.read()
            if not success:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            lower_skin = np.array([0, 20, 50], dtype=np.uint8)
            upper_skin = np.array([25, 200, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)

            contours, _ = cv2.findContours(
                mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            if contours:
                max_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(max_contour)

                if area > 3500:
                    bx, by, bw, bh = cv2.boundingRect(max_contour)
                    M = cv2.moments(max_contour)

                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])

                        # Normalize positions (-1.0 to 1.0)
                        norm_x = round((cx - (w / 2)) / (w / 2), 2)
                        norm_y = round(-((cy - (h / 2)) / (h / 2)), 2)
                        scale = round(
                            max(0.6, min(2.8, area / 18000.0)), 2
                        )

                        # Update 3D reactor position & zoom in GUI
                        if gui_instance and gui_instance.is_alive():
                            try:
                                gui_instance.window.evaluate_js(
                                    f"window.updateArcTransform({norm_x}, {norm_y}, {scale});"
                                )
                            except Exception:
                                pass

                        # Gestures: Thumbs Up / Down
                        aspect_ratio = float(bw) / float(bh)
                        relative_cy = (cy - by) / float(bh)
                        current_time = time.time()

                        if aspect_ratio < 0.85 and area > 5000:
                            if (
                                relative_cy < 0.46
                                and current_time - last_gesture_time > 1.8
                            ):
                                change_volume_relative(10)
                                if gui_instance and gui_instance.is_alive():
                                    gui_instance.append_log(
                                        "[GESTURE] Thumbs Up: Volume +10%"
                                    )
                                last_gesture_time = current_time

                            elif (
                                relative_cy > 0.54
                                and current_time - last_gesture_time > 1.8
                            ):
                                change_volume_relative(-10)
                                if gui_instance and gui_instance.is_alive():
                                    gui_instance.append_log(
                                        "[GESTURE] Thumbs Down: Volume -10%"
                                    )
                                last_gesture_time = current_time

            time.sleep(0.03)

        cap.release()

    tracker_thread = threading.Thread(target=track, daemon=True)
    tracker_thread.start()