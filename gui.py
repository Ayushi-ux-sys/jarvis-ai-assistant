import webview


class JarvisWebGUI:

    def __init__(self, on_command_received=None):
        self.on_command_received = on_command_received
        self.window = None
        self.is_running = True

    def _on_closed(self):
        """Triggered automatically when the user closes the window."""
        self.is_running = False
        self.window = None

    def start_gui(self):
        class Api:

            def __init__(parent_self):
                self.parent = parent_self

            def send_command(api_self, text):
                if self.on_command_received:
                    self.on_command_received(text)

        self.window = webview.create_window(
            "J.A.R.V.I.S. HUD INTERFACE",
            "templates/index.html",
            js_api=Api(self),
            width=1280,
            height=720,
            resizable=True,
        )
        self.window.events.closed += self._on_closed

    def is_alive(self) -> bool:
        return self.is_running and self.window is not None

    def _safe_evaluate_js(self, js_code: str):
        """Executes JavaScript safely, swallowing ObjectDisposedExceptions if the window is closed."""
        if not self.is_alive():
            return
        try:
            self.window.evaluate_js(js_code)
        except Exception:
            self.is_running = False
            self.window = None

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