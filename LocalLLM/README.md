# Local Ollama Chat (macOS)

A single-file ChatGPT-style interface for your local Ollama models (Qwen, DeepSeek, etc.).

## One-time setup

1. Install Ollama:
   ```bash
   brew install ollama
   ```
   Or download from https://ollama.com/download/mac
2. Drop both files (`index.html`, `start-chat.command`) into the same folder.

## Usage

Double-click `start-chat.command`. Done.

The script will:
- Start the Ollama server if it isn't running
- Pull `qwen2.5` and `deepseek-r1` on first run (skips after that)
- Open the chat UI in your default browser

### If macOS blocks the .command file

First time only, you may see "cannot be opened because it is from an unidentified developer."
Right-click the file → Open → Open. After that, double-click works normally.

Or run from Terminal:
```bash
chmod +x start-chat.command
./start-chat.command
```

## Switching models

Use the dropdown at the top. To add more models, run in Terminal:

```bash
ollama pull llama3.2
ollama pull mistral
ollama pull deepseek-coder-v2
```

Then click ↻ Refresh in the UI.

## MacBook Pro sizing tips

| RAM    | Recommended models                              |
|--------|-------------------------------------------------|
| 8 GB   | qwen2.5:3b, llama3.2:3b, deepseek-r1:1.5b       |
| 16 GB  | qwen2.5:7b, deepseek-r1:7b, llama3.1:8b         |
| 32 GB+ | qwen2.5:14b, deepseek-r1:14b, qwen2.5:32b       |
| 64 GB+ | qwen2.5:72b, deepseek-r1:70b                    |

Apple Silicon (M1/M2/M3/M4) handles these much better than Intel Macs thanks to unified memory.

To pull a specific size: `ollama pull qwen2.5:7b`

## Notes

- All inference is 100% local. Nothing leaves your machine.
- Conversation history is in-memory only (clears on reload).
- Stop the Ollama server anytime: `pkill ollama`
- Browse models: https://ollama.com/library
