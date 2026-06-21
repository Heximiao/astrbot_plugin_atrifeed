import json
import tkinter as tk
import urllib.request


class ChatBox(tk.Toplevel):
    def __init__(self, master, api_url: str, on_reply):
        super().__init__(master)
        self.api_url = api_url.rstrip("/")
        self.on_reply = on_reply
        self.title("ATRI")
        self.resizable(False, False)
        self.geometry("360x96")
        self.entry = tk.Entry(self, font=("Microsoft YaHei UI", 10))
        self.entry.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.entry.bind("<Return>", self._send)
        button = tk.Button(self, text="发送", command=self._send)
        button.pack(anchor=tk.E, padx=8)
        self.withdraw()

    def open_near(self, x: int, y: int):
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.entry.focus_set()

    def _send(self, *_):
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, tk.END)
        try:
            payload = json.dumps({"message": message}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_url}/pet/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=50) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.on_reply(data.get("reply", "嗯。"), data.get("action", "idle"))
        except Exception:
            self.on_reply("现在好像连不上插件侧服务。", "sit")
