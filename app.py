import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

# A packaged windowed app has no console, so stdout/stderr can be None.
# Some libraries crash when they try to print, so give them a dummy file.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import extractor  # our processing code (extractor.py)


def open_path(path):
    """Open a file or folder with the default program."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("YouTube Whiteboard Extractor")
        self.geometry("560x300")
        self.resizable(False, False)
        self.set_icon()

        self.messages = queue.Queue()
        self.pdf_path = None

        self.build_widgets()
        self.after(100, self.check_messages)

    def set_icon(self):
        try:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            self.app_icon = tk.PhotoImage(file=str(base / "icon.png"))
            self.iconphoto(True, self.app_icon)
        except Exception:
            pass  # no icon file found: keep the default icon

    # ---------------- layout ----------------

    def build_widgets(self):
        pad = {"padx": 20}

        ttk.Label(
            self,
            text="Turn a YouTube lecture into PDF notes",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(pady=(18, 4), **pad)

        ttk.Label(self, text="Paste the YouTube link:").pack(anchor="w", pady=(8, 2), **pad)

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(row, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.focus()

        ttk.Button(row, text="Paste", width=7, command=self.paste_url).pack(side="left", padx=(6, 0))

        self.start_button = ttk.Button(self, text="Start", command=self.start)
        self.start_button.pack(pady=14)

        self.stage_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.stage_var).pack(anchor="w", **pad)

        self.progress = ttk.Progressbar(self, maximum=100, length=520)
        self.progress.pack(pady=(4, 10), **pad)

        self.result_row = ttk.Frame(self)
        self.result_row.pack()

        self.open_pdf_button = ttk.Button(self.result_row, text="Open PDF", command=self.open_pdf)
        self.open_folder_button = ttk.Button(self.result_row, text="Open folder", command=self.open_folder)

    # ---------------- actions ----------------

    def paste_url(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def start(self):
        url = self.url_var.get().strip()

        if not url:
            messagebox.showwarning("No link", "Please paste a YouTube link first.")
            return

        self.start_button.config(state="disabled")
        self.open_pdf_button.pack_forget()
        self.open_folder_button.pack_forget()
        self.progress["value"] = 0
        self.stage_var.set("Starting...")

        threading.Thread(target=self.worker, args=(url,), daemon=True).start()

    def worker(self, url):
        """Runs in a background thread so the window never freezes."""

        def on_progress(stage, percent):
            self.messages.put(("progress", stage, percent))

        def on_status(text):
            self.messages.put(("status", text))

        try:
            pdf_path = extractor.process_video(url, on_progress, on_status)
            self.messages.put(("done", pdf_path))
        except Exception as error:
            self.messages.put(("error", str(error)))

    def check_messages(self):
        """Runs in the window thread and applies updates from the worker."""
        try:
            while True:
                message = self.messages.get_nowait()
                kind = message[0]

                if kind == "progress":
                    _, stage, percent = message
                    self.progress["value"] = percent
                    self.stage_var.set(f"{stage}... {percent:.0f}%")

                elif kind == "status":
                    self.stage_var.set(message[1])

                elif kind == "done":
                    self.pdf_path = message[1]
                    self.progress["value"] = 100
                    self.stage_var.set("Done! Your PDF is ready.")
                    self.start_button.config(state="normal")
                    self.open_pdf_button.pack(side="left", padx=5)
                    self.open_folder_button.pack(side="left", padx=5)

                elif kind == "error":
                    self.stage_var.set("Something went wrong.")
                    self.start_button.config(state="normal")
                    messagebox.showerror("Error", message[1])

        except queue.Empty:
            pass

        self.after(100, self.check_messages)

    def open_pdf(self):
        if self.pdf_path:
            open_path(self.pdf_path)

    def open_folder(self):
        if self.pdf_path:
            open_path(self.pdf_path.parent)


if __name__ == "__main__":
    App().mainloop()