import os
import subprocess
import sys
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from desktop import Desktop
from jarvis import Assistant
from voice import Dictation


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "requires a desktop display")
class VoiceFlow(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.assistant = Assistant(":memory:")
        self.addCleanup(self.assistant.db.close)
        self.window = Desktop(self.root, self.assistant)
        self.window.entry.insert(0, "Remember")

    def speak(self, script):
        proc = subprocess.Popen([sys.executable, "-u", "-c", script], stdout=subprocess.PIPE)
        self.addCleanup(proc.wait, 3)
        self.addCleanup(proc.kill)
        with patch("desktop.start_dictation", return_value=Dictation(proc)):
            self.window.voice_button.invoke()
        return proc

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_voice_only_appends_a_draft(self):
        self.speak('import sys; sys.stdout.buffer.write("READY en-IN\\nAtlas café\\n".encode())')
        self.wait_for(lambda: self.window.dictation is None)
        self.assertEqual(self.window.entry.get(), "Remember Atlas café")
        self.assertEqual(self.assistant.history(), [])
        self.assertFalse(self.window.send_button.instate(["disabled"]))

    def test_cancel_releases_process_and_preserves_typed_text(self):
        proc = self.speak('import time; print("READY en-IN"); time.sleep(60)')
        self.wait_for(lambda: "Listening (" in self.window.status.get())
        self.window.send()
        self.window.voice_button.invoke()
        self.wait_for(lambda: proc.poll() is not None)
        self.assertEqual(self.window.entry.get(), "Remember")
        self.assertFalse(self.window.send_button.instate(["disabled"]))
        self.assertEqual(self.assistant.history(), [])

    def test_missing_microphone_recovers(self):
        with patch("desktop.messagebox.showerror") as error:
            self.speak("raise SystemExit(3)")
            self.wait_for(lambda: self.window.dictation is None)
        self.assertIn("default microphone", error.call_args.args[1])
        self.assertEqual(self.window.entry.get(), "Remember")
        self.assertFalse(self.window.send_button.instate(["disabled"]))
