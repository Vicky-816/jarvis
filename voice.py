"""Capture one utterance with Windows' installed offline speech recognizer."""
import os
import queue
import subprocess
import threading
from pathlib import Path

# The helper receives no user input. Its stdout reports readiness, then one phrase.
RECOGNIZE = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$engine = $null
try {
    Add-Type -AssemblyName System.Speech
    $installed = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers())
    if ($installed.Count -eq 0) { exit 2 }
    $recognizer = $installed | Where-Object { $_.Culture.Name -eq (Get-Culture).Name } | Select-Object -First 1
    if ($null -eq $recognizer) { $recognizer = $installed[0] }
    $engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($recognizer)
    $grammar = [System.Speech.Recognition.DictationGrammar]::new()
    $engine.LoadGrammar($grammar)
    try { $engine.SetInputToDefaultAudioDevice() } catch { exit 3 }
    $engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(8)
    [Console]::WriteLine('READY ' + $recognizer.Culture.Name)
    $result = $engine.Recognize([TimeSpan]::FromSeconds(8))
    if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) { exit 4 }
    [Console]::WriteLine($result.Text)
} catch { exit 5 }
finally { if ($null -ne $engine) { $engine.Dispose() } }
"""

ERRORS = {
    2: "Install speech recognition for a supported language in Windows language settings, then try again.",
    3: "Check your default microphone and allow microphone access for desktop apps in Windows Settings.",
    4: "No speech recognized. Try again and speak after the listening indicator appears.",
}


def start_dictation():
    if os.name != "nt":
        raise ValueError("Local dictation requires Windows.")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    proc = subprocess.Popen(
        [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", RECOGNIZE],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return Dictation(proc)


class Dictation:
    def __init__(self, process):
        self.process = process
        self.events = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            with self.process.stdout as stream:
                ready = stream.readline().decode("utf-8-sig").strip()
                if ready.startswith("READY "):
                    self.events.put(("listening", ready[6:]))
                phrase = stream.read().decode("utf-8").strip()
            code = self.process.wait()
            if code == 0 and ready.startswith("READY ") and phrase:
                self.events.put(("draft", phrase))
            else:
                self.events.put(("error", ERRORS.get(code, "Windows could not start dictation. Check your speech language and microphone settings.")))
        except (OSError, UnicodeError):
            self.cancel()
            self.events.put(("error", "Could not read the Windows dictation result."))

    def cancel(self):
        if self.process.poll() is None:
            self.process.kill()
