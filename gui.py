import os
import webview

command_callback = None


class JSAPI:

    def send_command(self, text: str):
        global command_callback
        if command_callback and text:
            command_callback(text)


class JarvisWebGUI:

    def __init__(self, on_command_received=None):
        global command_callback
        command_callback = on_command_received

        base_dir = os.path.dirname(os.path.abspath(__file__))

        html_path = os.path.join(base_dir, "template", "index.html")
        if not os.path.exists(html_path):
            html_path = os.path.join(base_dir, "templates", "index.html")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        api = JSAPI()
        self.window = webview.create_window(
            title="J.A.R.V.I.S. HUD INTERFACE",
            html=html_content,
            js_api=api,
            width=1150,
            height=740,
            resizable=True,
            background_color="#030a12",
        )

    def is_alive(self) -> bool:
        """Helper to check if the webview window is valid and open."""
        try:
            return self.window is not None and len(webview.windows) > 0
        except Exception:
            return False

    def update_state(self, status_text: str, color_hex: str):
        if not self.is_alive():
            return
        try:
            self.window.evaluate_js(
                f"window.updateStatus('{status_text}', '{color_hex}');"
            )
        except Exception:
            pass

    def append_log(self, text: str):
        if not self.is_alive():
            return
        try:
            clean_text = (
                text.replace("'", "\\'").replace("\n", " ").replace("\r", "")
            )
            self.window.evaluate_js(f"window.addLog('{clean_text}');")
        except Exception:
            pass

    def update_thinking(self, prompt: str, step: str = "", action: str = ""):
        if not self.is_alive():
            return
        try:
            clean_prompt = (
                prompt.replace("'", "\\'").replace("\n", " ").replace("\r", "")
            )
            clean_step = (
                step.replace("'", "\\'").replace("\n", " ").replace("\r", "")
            )
            clean_action = (
                action.replace("'", "\\'").replace("\n", " ").replace("\r", "")
            )
            js_code = f"window.updateThinking({{prompt: '{clean_prompt}', step: '{clean_step}', action: '{clean_action}'}});"
            self.window.evaluate_js(js_code)
        except Exception:
            pass

    def update_system_stats(self, cpu: int, ram: int):
        if not self.is_alive():
            return
        try:
            self.window.evaluate_js(f"window.updateStats({cpu}, {ram});")
        except Exception:
            pass


def start_gui():
    gui = JarvisWebGUI()
    webview.start()


if __name__ == "__main__":
    start_gui()