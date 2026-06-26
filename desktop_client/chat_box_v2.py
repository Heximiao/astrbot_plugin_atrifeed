import json
import threading
import tkinter as tk
import urllib.request


class ChatBox(tk.Toplevel):
    def __init__(self, master, api_url: str, on_reply):
        super().__init__(master)
        self.api_url = api_url.rstrip("/")
        self.on_reply = on_reply
        self._busy = False
        self.title("ATRI")
        self.resizable(False, False)
        self.geometry("360x96")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.entry = tk.Entry(self, font=("Microsoft YaHei UI", 10))
        self.entry.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.entry.bind("<Return>", self._send)
        self.button = tk.Button(self, text="Send", command=self._send)
        self.button.pack(anchor=tk.E, padx=8)
        self.withdraw()

    def open_near(self, x: int, y: int):
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.entry.focus_set()

    def _send(self, *_):
        if self._busy:
            return
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, tk.END)
        self._set_busy(True)
        threading.Thread(target=self._request_reply, args=(message,), daemon=True).start()

    def _request_reply(self, message: str):
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
            reply = data.get("reply") or "OK."
            action = data.get("action") or "idle"
        except Exception:
            reply = "Cannot connect to plugin service right now."
            action = "sit"
        self.after(0, self._finish_reply, reply, action)

    def _finish_reply(self, reply: str, action: str):
        self._set_busy(False)
        self.on_reply(reply, action)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.button.configure(state=tk.DISABLED if busy else tk.NORMAL)
