"""Windows desktop entry point for Jarvis."""
import os
import queue
import sqlite3
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from jarvis import Assistant, model_reply, open_workspace
from voice import start_dictation


class Desktop:
    def __init__(self, root, assistant):
        self.root, self.assistant = root, assistant
        root.title("Jarvis")
        root.geometry("780x560")
        root.minsize(540, 380)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=16)
        self.chat = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.chat, text="Conversation")
        self.transcript = ScrolledText(self.chat, wrap="word", state="disabled", font=("Segoe UI", 11),
                                       padx=14, pady=12, relief="flat", height=8)
        self.transcript.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Messages are processed on this computer.")
        ttk.Label(self.chat, textvariable=self.status).pack(anchor="w", pady=8)
        bar = ttk.Frame(self.chat)
        bar.pack(fill="x")
        self.entry = ttk.Entry(bar, font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _: self.send())
        self.send_button = ttk.Button(bar, text="Send", command=self.send)
        self.send_button.pack(side="right", padx=(8, 0))
        self.voice_button = ttk.Button(bar, text="Speak", command=self.toggle_voice)
        self.voice_button.pack(side="right", padx=(8, 0))
        self.dictation = None
        self.voice_timer = None
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.records = {}
        for label in ("Memory", "Workspaces"):
            page = ttk.Frame(self.tabs, padding=12)
            self.tabs.add(page, text=label)
            rows = tk.Listbox(page, font=("Segoe UI", 11), exportselection=False)
            rows.pack(fill="both", expand=True)
            self.records[label] = rows
            buttons = ttk.Frame(page)
            buttons.pack(fill="x", pady=(10, 0))
            actions = ([("Add memory", self.add_note), ("View or edit", self.edit_note),
                        ("Forget", self.forget), ("Clear conversation", self.clear_chat)]
                       if label == "Memory" else
                       [("Register folder", self.register), ("Remove", self.unregister)])
            for title, callback in actions:
                ttk.Button(buttons, text=title, command=callback).pack(side="left", padx=(0, 5))
        self.refresh()
        for role, text in assistant.history():
            self.line(role, text)
        self.entry.focus_set()

    def refresh(self):
        self.notes = self.assistant.notes()
        self.projects = self.assistant.projects()
        for key, labels in [("Memory", [f"{i} · {s}" for i, s, _ in self.notes]),
                            ("Workspaces", [f"{n} · {d} · {p}" for n, d, p in self.projects])]:
            rows = self.records[key]
            rows.delete(0, "end")
            for label in labels:
                rows.insert("end", label)

    def selected(self, key, data):
        selected = self.records[key].curselection()
        if selected:
            return data[selected[0]]
        messagebox.showinfo("Jarvis", "Select an item first.")

    def add_note(self):
        text = simpledialog.askstring("Memory", "What should Jarvis remember?")
        if text:
            self.assistant.remember(text, "Entered by you")
            self.refresh()

    def edit_note(self):
        note = self.selected("Memory", self.notes)
        if note:
            text = simpledialog.askstring("Memory", f"Source: {note[2]}\n\nMemory:", initialvalue=note[1])
            if text:
                self.assistant.remember(text, "Edited by you", note[0])
                self.refresh()

    def forget(self):
        note = self.selected("Memory", self.notes)
        if note and messagebox.askyesno("Forget memory", "Remove this saved note? Past chat messages are kept."):
            with self.assistant.db:
                self.assistant.db.execute("DELETE FROM memory WHERE id=?", (note[0],))
            self.refresh()

    def clear_chat(self):
        if messagebox.askyesno("Clear conversation", "Delete the conversation from Jarvis? Saved notes are kept."):
            with self.assistant.db:
                self.assistant.db.execute("DELETE FROM messages")
            self.transcript.configure(state="normal")
            self.transcript.delete("1.0", "end")
            self.transcript.configure(state="disabled")

    def register(self):
        name = simpledialog.askstring("Workspace", "Project name")
        if not name:
            return
        distro = simpledialog.askstring("Workspace", "WSL distribution", initialvalue="Ubuntu")
        if not distro:
            return
        path = simpledialog.askstring("Workspace", "Project folder in WSL, e.g. /home/me/atlas")
        if path:
            try:
                self.assistant.register(name, distro, path)
            except sqlite3.IntegrityError:
                raise ValueError("That project name already exists.") from None
            self.refresh()

    def unregister(self):
        row = self.selected("Workspaces", self.projects)
        if row and messagebox.askyesno("Remove workspace", f"Remove {row[0]} from Jarvis? Your files are kept."):
            with self.assistant.db:
                self.assistant.db.execute("DELETE FROM projects WHERE name=?", (row[0],))
            self.refresh()

    def line(self, role, text):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{'You' if role == 'user' else 'Jarvis'}\n{text}\n\n")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def background(self, status, task, success, failure=None):
        results = queue.Queue()
        def run():
            try:
                results.put((True, task()))
            except Exception as exc:
                results.put((False, exc))

        self.send_button.state(["disabled"])
        self.voice_button.state(["disabled"])
        self.entry.state(["disabled"])
        for idx in (1, 2):
            self.tabs.tab(idx, state="disabled")
        self.status.set(status)
        threading.Thread(target=run, daemon=True).start()

        def poll():
            if results.empty():
                self.root.after(100, poll)
                return
            ok, result = results.get()
            self.send_button.state(["!disabled"])
            self.voice_button.state(["!disabled"])
            self.entry.state(["!disabled"])
            for idx in (1, 2):
                self.tabs.tab(idx, state="normal")
            self.status.set("Ready")
            if ok:
                success(result)
            else:
                self.status.set("Action failed")
                if failure:
                    failure(str(result))
                messagebox.showerror("Jarvis", str(result))
            self.entry.focus_set()
        self.root.after(100, poll)

    def close(self):
        if self.dictation:
            self.finish_voice("Dictation cancelled.")
        self.root.destroy()

    def toggle_voice(self):
        if self.dictation:
            self.finish_voice("Dictation cancelled.")
            return
        session = start_dictation()
        self.dictation = session
        deadline = time.monotonic() + 35
        self.voice_button.configure(text="Cancel mic")
        self.send_button.state(["disabled"])
        for idx in (1, 2):
            self.tabs.tab(idx, state="disabled")
        self.status.set("Starting microphone… Wait for Listening.")

        def poll():
            self.voice_timer = None
            if session is not self.dictation:
                return
            try:
                event, value = session.events.get_nowait()
            except queue.Empty:
                if time.monotonic() >= deadline:
                    self.finish_voice("Dictation timed out. Try a shorter phrase.")
                    return
            else:
                if event == "draft":
                    separator = " " if self.entry.get() and not self.entry.get()[-1].isspace() else ""
                    self.entry.insert("end", separator + value)
                    self.entry.xview_moveto(1)
                    self.finish_voice("Review your words, then select Send.")
                    return
                if event == "error":
                    self.finish_voice("Dictation stopped.")
                    messagebox.showerror("Voice input", value)
                    return
                self.status.set(f"Listening ({value})… Speak one phrase, then pause.")
            self.voice_timer = self.root.after(80, poll)
        self.voice_timer = self.root.after(80, poll)

    def finish_voice(self, status):
        if self.voice_timer is not None:
            self.root.after_cancel(self.voice_timer)
            self.voice_timer = None
        self.dictation.cancel()
        self.dictation = None
        self.voice_button.configure(text="Speak")
        self.send_button.state(["!disabled"])
        for idx in (1, 2):
            self.tabs.tab(idx, state="normal")
        self.status.set(status)
        self.entry.focus_set()

    def send(self):
        request = self.entry.get().strip()
        if not request or self.send_button.instate(["disabled"]):
            return
        messages, notes, projects = self.assistant.context(request)

        def receive(result):
            reply, memory, project = self.assistant.receive(request, result, notes, projects)
            self.entry.delete(0, "end")
            self.line("user", request)
            self.line("assistant", reply)
            if memory:
                original = notes.get(memory.get("id"))
                prompt = ("Replace this memory?\n\n" + original + "\n\nWith:\n" if original
                          else "Save this memory?\n\n")
                if messagebox.askyesno("Memory proposal", prompt + memory["text"]):
                    self.assistant.remember(memory["text"], request, memory.get("id"))
                    self.refresh()
                    self.outcome("Memory saved.")
                else:
                    self.outcome("Memory change declined.")
            elif project:
                _, distro, path = next(row for row in self.projects if row[0] == project)
                if messagebox.askyesno("Open workspace", f"Open {project} in VS Code?\n\n{distro} · {path}"):
                    self.background("Opening workspace…", lambda: open_workspace(distro, path), self.outcome,
                                    lambda error: self.outcome("Workspace open failed: " + error))
                else:
                    self.outcome("Open request declined.")
        self.background("Waiting for the local model…", lambda: model_reply(messages), receive)

    def outcome(self, text):
        self.assistant.record_outcome(text)
        self.line("assistant", text)


def main():
    root = tk.Tk()
    data = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "Jarvis"
    data.mkdir(parents=True, exist_ok=True)
    assistant = Assistant(data / "assistant.sqlite3")
    root.report_callback_exception = lambda kind, exc, tb: messagebox.showerror("Jarvis", str(exc))
    Desktop(root, assistant)
    try:
        root.mainloop()
    finally:
        assistant.db.close()


if __name__ == "__main__":
    main()
