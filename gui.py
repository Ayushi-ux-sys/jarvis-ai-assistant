import os
import webview

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "template", "index.html")


class Api:
    """Decoupled JS API class to avoid COM recursion and disposal conflicts."""

    def __init__(self, callback):
        self._callback = callback

    def send_command(self, text):
        if self._callback:
            self._callback(text)


class JarvisWebGUI:

    def __init__(self, on_command_received=None):
        self.on_command_received = on_command_received
        self.window = None
        self.is_running = True
        self.is_ready = False

    def _on_loaded(self):
        self.is_ready = True

    def _on_closed(self):
        """Immediately flag window as unavailable to stop background thread JS execution."""
        self.is_ready = False
        self.is_running = False
        self.window = None

    def start_gui(self):
        if not os.path.exists(INDEX_HTML_PATH):
            print(f"[GUI ERROR] Cannot find template at: {INDEX_HTML_PATH}")

        api_instance = Api(self.on_command_received)

        self.window = webview.create_window(
            "J.A.R.V.I.S. HUD INTERFACE",
            INDEX_HTML_PATH,
            js_api=api_instance,
            width=1280,
            height=720,
            resizable=True,
        )
        self.window.events.loaded += self._on_loaded
        self.window.events.closed += self._on_closed

    def is_alive(self) -> bool:
        return self.is_running and self.is_ready and self.window is not None

    def _safe_evaluate_js(self, js_code: str):
        """Safely dispatches JS to the UI thread, suppressing ObjectDisposedExceptions."""
        if not self.is_alive():
            return
        try:
            self.window.evaluate_js(js_code)
        except Exception:
            # Silently catch and suppress disposed object errors during shutdown
            self.is_ready = False

    def update_state(self, status: str, color: str):
        self._safe_evaluate_js(
            f"if(window.updateStatus) window.updateStatus('{status}', '{color}');"
        )

    def append_log(self, text: str):
        safe_text = (
            text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        )
        self._safe_evaluate_js(
            f"if(window.addLog) window.addLog('{safe_text}');"
        )

    def update_thinking(
        self, prompt: str, step: str = "", action: str = ""
    ):
        safe_prompt = prompt.replace("'", "\\'")
        safe_step = step.replace("'", "\\'")
        safe_action = action.replace("'", "\\'")
        js_payload = f"{{ prompt: '{safe_prompt}', step: '{safe_step}', action: '{safe_action}' }}"
        self._safe_evaluate_js(
            f"if(window.updateThinking) window.updateThinking({js_payload});"
        )

    def update_system_stats(self, cpu: int, ram: int):
        self._safe_evaluate_js(
            f"if(window.updateStats) window.updateStats({cpu}, {ram});"
        )