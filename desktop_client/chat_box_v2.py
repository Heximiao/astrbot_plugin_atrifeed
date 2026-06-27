import threading
import tkinter as tk

from pet_api_client import request_chat


class ChatBox(tk.Toplevel):
    def __init__(self, master, api_url: str, on_reply, get_user_id=None):
        super().__init__(master)
        self.api_url = api_url.rstrip("/")
        self.on_reply = on_reply
        self.get_user_id = get_user_id
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
        threading.Thread(target=self._request_chat_worker, args=(message,), daemon=True).start()

    def _request_chat_worker(self, message: str):
        try:
            reply, action = request_chat(
                self.api_url,
                message,
                self.get_user_id() if self.get_user_id else "",
            )
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
