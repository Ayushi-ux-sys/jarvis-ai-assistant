import os
import webview


class JarvisWebGUI:

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        html_path = os.path.join(base_dir, "template", "index.html")
        if not os.path.exists(html_path):
            html_path = os.path.join(base_dir, "templates", "index.html")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        self.window = webview.create_window(
            title="J.A.R.V.I.S. HUD INTERFACE",
            html=html_content,
            width=1100,
            height=720,
            resizable=True,
            background_color="#030a12",
        )

    def update_state(self, status_text: str, color_hex: str):
        try:
            if self.window:
                self.window.evaluate_js(
                    f"window.updateStatus('{status_text}', '{color_hex}');"
                )
        except Exception:
            pass

    def append_log(self, text: str):
        try:
            clean_text = text.replace("'", "\\'").replace("\n", " ")
            if self.window:
                self.window.evaluate_js(f"window.addLog('{clean_text}');")
        except Exception:
            pass

    def update_system_stats(self, cpu: int, ram: int):
        try:
            if self.window:
                self.window.evaluate_js(f"window.updateStats({cpu}, {ram});")
        except Exception:
            pass


def start_gui():
    gui = JarvisWebGUI()
    webview.start()


if __name__ == "__main__":
    start_gui()