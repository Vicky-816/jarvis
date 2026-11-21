import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from jarvis import Assistant


class MemoryFlow(unittest.TestCase):
    def test_correction_and_citation_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assistant.sqlite3"
            assistant = Assistant(path)
            assistant.remember("Atlas uses SQLite.", "Remember Atlas uses SQLite.")
            note_id = assistant.notes()[0][0]
            request = "Actually it uses Postgres."
            _, notes, projects = assistant.context(request)
            _, memory, _ = assistant.receive(request, {
                "reply": "Save the correction?", "sources": [note_id],
                "memory": {"id": note_id, "text": "Atlas uses Postgres."}}, notes, projects)
            self.assertEqual(assistant.notes()[0][1], "Atlas uses SQLite.")
            assistant.remember(memory["text"], request, memory["id"])
            assistant.db.close()
            assistant = Assistant(path)
            self.addCleanup(assistant.db.close)
            messages, notes, projects = assistant.context("What database do we use?")
            self.assertIn(request, [m["content"] for m in messages])
            self.assertEqual(assistant.notes(), [(note_id, "Atlas uses Postgres.", request)])
            reply, _, _ = assistant.receive("What database do we use?", {
                "reply": "Postgres.", "sources": [note_id]}, notes, projects)
            self.assertIn("Atlas uses Postgres.", reply)

    def test_invented_targets_and_citations_rejected(self):
        assistant = Assistant(":memory:")
        self.addCleanup(assistant.db.close)
        for extra in [{"open_project": "made up"}, {"sources": [900]}, {"memory": {"id": 5, "text": "x"}}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                assistant.receive("hello", {"reply": "ok", **extra}, {}, [])
        self.assertEqual(assistant.history(), [])


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "requires a desktop display")
class DesktopFlow(unittest.TestCase):
    def test_approved_memory_through_chat_window_and_http(self):
        import tkinter as tk
        from desktop import Desktop
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                response = {"reply": "Shall I remember that?", "sources": [],
                            "memory": {"text": "Atlas is a music project."}}
                body = json.dumps({"message": {"content": json.dumps(response)}}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        root = tk.Tk()
        self.addCleanup(root.destroy)
        assistant = Assistant(":memory:")
        self.addCleanup(assistant.db.close)
        app = Desktop(root, assistant)
        from http.client import HTTPConnection
        def local_connection(host, port, **kwargs):
            self.assertEqual((host, port), ("127.0.0.1", 11434))
            return HTTPConnection(host, server.server_port, **kwargs)

        with patch("jarvis.http.client.HTTPConnection", local_connection), patch(
                "desktop.messagebox.askyesno", return_value=True), patch("desktop.messagebox.showerror"):
            app.entry.insert(0, "Remember Atlas is a music project.")
            app.send_button.invoke()
            deadline = time.monotonic() + 5
            while not assistant.notes() and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
        self.assertEqual(requests[0][0], "/api/chat")
        self.assertEqual(requests[0][1]["messages"][-1]["content"], "Remember Atlas is a music project.")
        self.assertEqual(assistant.notes()[0][1], "Atlas is a music project.")
        self.assertIn("Memory saved.", app.transcript.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
