# Jarvis

A personal assistant for Windows that talks to a local language model. This first development version includes typed and dictated conversation, a notebook you control, and a way to open registered WSL projects in VS Code. Messages go to Ollama on your own computer. No API key or paid account is required.

## Start on your Windows laptop

1. Install [Python 3.12 or later for Windows](https://www.python.org/downloads/windows/). Include the Python launcher and Tcl/Tk in the installer.
2. Install and open [Ollama for Windows](https://ollama.com/download/windows).
3. Open PowerShell and run `ollama pull qwen2.5:3b` once. It downloads the local model. Allow a few GB of free disk space.
4. With the project files together in a folder, double-click **Start Jarvis.cmd**.
5. Type something you would like it to remember, for example “I'm working on Atlas, a tool for organizing my music. Last time I was fixing the import screen.” Review any proposed note before saving it. Close Jarvis, reopen it, and ask “Where did I leave off with Atlas?” Open **Memory** to see the source of a saved note or correct it yourself.

The model may take a while to load on an 8 GB laptop. If Jarvis reports that Ollama did not respond, open Ollama and try again. The Memory and Workspaces tabs also work while Ollama is offline.

## Speak a message on Windows

Open **Conversation**, click **Speak**, and wait for **Listening**. Say one short sentence into your default microphone, then pause. Jarvis appends the recognized words to the message box. Edit them and click **Send** when ready. **Cancel mic** discards that attempt and keeps any text you already typed.

Dictation uses the installed Windows desktop speech recognizer, with the current Windows culture preferred when available. The Listening indicator shows the language in use. Audio stays on the laptop. The app stores no audio files, and you can test dictation before starting Ollama. Sending the resulting message uses the same local chat and history as typing.

If recognition is unavailable, open **Settings → Time & language → Language & region**, then the language's options, and install **Basic speech recognition** or **Speech** for a supported language. If the microphone is unavailable, check **Settings → System → Sound → Input** and **Privacy & security → Microphone → Let desktop apps access your microphone**.

## Open a project

Install VS Code for Windows in its standard location, the Microsoft WSL extension, and a WSL distribution. Open **Workspaces → Register folder** and enter a name, your distribution, and an existing absolute Linux folder path. In PowerShell, `wsl -l -q` lists distribution names. In your project's WSL terminal, `pwd` prints the folder path.

Tell Jarvis which project you want to work on. When it proposes opening a project, the app shows its registered folder for your approval. Jarvis checks that the folder exists and sends the request to VS Code. Check the editor window to confirm it opened.

## Your records

Chat, saved notes, and workspace registrations are stored in a SQLite file under `%LOCALAPPDATA%\Jarvis`. This file uses the privacy protections of your Windows account and disk. Jarvis gives the model recent conversation turns, recent saved notes and registered workspace names. The model does not read your project files. You can delete notes and clear the conversation independently. A saved note keeps its source until you edit or delete the note.

This release runs on the laptop. Remote access from Android and iPad, and background notifications are future milestones. Local model performance and WSL launching require validation on your Windows setup.

## Develop

From this folder, run `python desktop.py` using Python 3.12+ with Tk. Run `python -m unittest -v` for the tests. The desktop flow test needs a graphical session and uses a local HTTP fixture for the model response. To check the actual model, use the conversation and restart exercise above.
