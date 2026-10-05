<div align="center">
  <h1>AI Assistant for LibreOffice</h1>
  <p><strong>An AI agent with access to your document: it reads, edits, builds charts and pivot tables</strong></p>
</div>

**Language:** [Русский](README.md) (main) · English · [中文（简体）](README.zh-CN.md)

<div align="center">

[![⚠ THE MODEL SEES PERSONAL DATA IN YOUR DOCUMENTS — de-identify before sending](https://img.shields.io/badge/⚠_THE_MODEL_SEES_PERSONAL_DATA_IN_YOUR_DOCUMENTS-de-identify_before_sending-c0392b?style=for-the-badge)](https://iustitia.tech/incognito/)

</div>

> **⚠️ Privacy.** In “Work with the document” (agent) mode and whenever document context is
> enabled, the document content (text, cells, selection) is sent to the selected AI
> provider — meaning the model **sees the personal data contained in the document**.
> If your document contains PII, de-identify it first. Quick options:
> **[Incognito Web](https://iustitia.tech/incognito/demo/)** (runs in the browser, no
> installation) or **[Incognito Desktop](https://iustitia.tech/incognito/)**
> (for regular use) — [iustitia.tech/incognito](https://iustitia.tech/incognito/).

<div align="center">

![version](https://img.shields.io/badge/version-1.13.0-2f8f8b?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-a6784f?style=flat-square)
![Python](https://img.shields.io/badge/Python-bundled%20with%20LO-1d2324?style=flat-square&logo=python&logoColor=f4efe6)
![LibreOffice](https://img.shields.io/badge/LibreOffice-26.8-185abd?style=flat-square&logo=libreoffice&logoColor=ffffff)
![platforms](https://img.shields.io/badge/Linux%20%7C%20Windows%20%7C%20macOS-x86__64-1d2324?style=flat-square&logo=linux&logoColor=f4efe6)

</div>

An AI assistant for LibreOffice (Writer, Calc, Impress, Draw) packaged as an `.oxt`
extension. Unlike ordinary “chat plugins”, the agent **sees the document content itself
and edits the document itself**: it reads cell ranges and document text, writes formulas,
builds charts, assembles pivot tables — from a plain-language request.

> Tested on: **Linux (Fedora), LibreOffice 26.8.1.1 (flatpak)**. Installation on Windows
> and macOS is supported (see [Installation](#installation)) but has not been verified on
> those systems yet.

---

## Contents

- [What it is](#what-it-is)
- [Features](#features)
- [The agent and its tools](#the-agent-and-its-tools)
- [Providers](#providers)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Security](#security)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

## What it is

A floating chat panel inside LibreOffice. In the basic mode it is a regular AI chat with
streaming output and quick one-click actions over text. With the **“Work with the
document (agent)”** checkbox enabled, the assistant becomes an agent: the model inspects
the document through tools, makes changes and verifies the result — no more copying text
into the chat by hand.

## Features

- **Agent with tools** (Writer and Calc): reads and edits the live document, every step
  is visible in the chat.
- **11 quick actions**: Chat, Improve text, Grammar & spelling, Summarize, Translate
  (target language configurable), Explain, Continue writing, Make shorter, Expand, Formal
  tone, Bullet list.
- **Result placement**: “Insert” (at the cursor), “Replace” (the selection), “Copy”.
- **Streaming output** with a Stop button; conversation history (8 turns, configurable).
- **17 provider presets** plus any custom endpoint; live model list fetched from the
  provider (Refresh button, auto-loaded after a successful connection test).
- **Panel window**: mouse-resizable by edges and corners (native, handled by the OS), the
  panel docks over the right-hand column of LibreOffice and follows the office window.
- **UI languages**: Russian / English / Chinese (auto-detected from the locale, or forced
  via `"ui_lang": "ru|en|zh"` in config.json).
- Standard-library Python only (no pip dependencies) — runs on the Python bundled with
  LibreOffice.

## The agent and its tools

The “Work with the document” checkbox enables the agent loop: the model is given a set of
tools and decides what to call; the result of every call is returned to the model until
the task is done (up to 12 steps, configurable — `agent_max_steps`).

Tools in **Calc**:

| Tool | What it does |
|---|---|
| `calc_info` | sheets of the workbook and their used ranges |
| `read_range` | cell values (optionally formulas) |
| `write_range` | write an array of values into a range |
| `set_formula` | put formulas into cells / a range |
| `sort_range` | sort by one or several keys |
| `format_range` | bold/italic, background and font colors, number format |
| `create_chart` | charts: column, bar, line, pie, area, scatter |
| `create_pivot` | pivot (consolidation) tables: row/column/data fields, sum, count, average, min, max aggregations |
| `find_replace` | find and replace across a sheet or the whole workbook |

Tools in **Writer**: document statistics, full-document and selection reading, selection
replacement, insert at cursor, find & replace.

Every edit is an ordinary LibreOffice operation and can be undone with **Ctrl+Z**. If the
model gets an argument wrong, it receives the error text and corrects itself.

## Providers

| Provider | API style | Where to get a key |
|---|---|---|
| **Z.ai Coding Plan (GLM)** — verified in real use | OpenAI | [z.ai/manage-apikey](https://z.ai/manage-apikey/apikey-list) |
| Z.ai Open Platform | OpenAI | same |
| **Anthropic Claude** | Messages | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| **OpenAI (GPT)** | OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) |
| **OpenAI Codex** | Responses | same |
| Google Gemini | OpenAI layer | [aistudio.google.com](https://aistudio.google.com/apikey) |
| OpenRouter, DeepSeek, Mistral, Groq, xAI, Together, Fireworks, Perplexity | OpenAI | provider consoles |
| Ollama, LM Studio (local, no key) | OpenAI | — |
| Custom | OpenAI | any compatible endpoint |

All 17 presets are covered by connection tests (each through its own API style, against
a local API mock: `tests/test_providers.py`). For OpenAI reasoning models
(`o1/o3/o4`, `gpt-5*`) the extension drops `temperature` and sends
`max_completion_tokens` automatically.

Agent mode requires a provider with function calling — that is every OpenAI-compatible
style (14 of 17 presets, including Z.ai GLM). Claude and Codex currently run in plain
chat mode (tools for those styles are planned).

## Installation

Identical on all three systems — via the extension manager:

1. Download `dist/sphaera-lo-ai-assistant.oxt` (or build it: `./build.sh`).
2. LibreOffice → **Tools ▸ Extension Manager… ▸ Add** → pick the file.
3. Fully restart LibreOffice — the **AI Assistant** menu and a toolbar button appear.

On Linux there is also a helper script: `./install.sh` (understands flatpak installs;
LibreOffice must be closed during installation).

Requirements: LibreOffice with Python scripting support (enabled by default in the
standard Windows, macOS and Linux installers).

## Quick start

1. **AI Assistant ▸ Settings…**: pick a preset — the URL and model fill in
   automatically → paste your API key → **Test connection** → **Save**.
2. **AI Assistant ▸ Open Panel…** — the panel docks over the right-hand column of the
   office window (or drag it by an edge wherever you like).
3. Ask a question or pick an action. With “Work with the document” enabled the agent
   reads and edits the document on its own: “build a chart from columns B:D”, “make a
   pivot table of sales by manager”, “improve the second paragraph”.

## Security

API keys are stored **locally only**, in a JSON config with `0600` permissions
(`…/user/config/lo-ai-assistant/config.json` inside the LibreOffice profile; outside the
office — `$APPDATA/lo-ai-assistant` or `$XDG_CONFIG_HOME/lo-ai-assistant`). Keys are sent
only to the API provider you choose. Never commit the config to git.

**About personal data** — see the warning at the top of the page: in agent mode, and
whenever document context is enabled, the document content goes to the AI provider you
selected. De-identify documents containing PII before working with them — for example
with [Incognito Web](https://iustitia.tech/incognito/demo/) or
[Incognito Desktop](https://iustitia.tech/incognito/).

## Development

```bash
python3 tests/test_providers.py   # adapters, config, prompts + connectivity of all presets
python3 tests/test_agent.py       # the agent loop (host python, no LO)
python3 tests/test_static.py      # static checks
./build.sh && ./install.sh        # build .oxt + install (Linux)
```

```
src/extension/
├── Addons.xcu                     # menu and toolbar button (service: dispatch)
├── Scripts/python/ai_assistant_entry.py   # python component (XJobExecutor) + macros
├── Scripts/python/pythonpath/lo_ai/
│   ├── agent.py                   # agent loop (model + tools)
│   ├── document_tools.py          # 15 tools over the live document (UNO)
│   ├── document_bridge.py         # document context for Writer/Calc/Impress/Draw
│   ├── assistant.py               # prompts, actions, history
│   ├── config.py, i18n.py, http_client.py, uno_env.py
│   ├── providers/                 # 17 presets; openai_compat / anthropic / responses
│   └── ui/                        # panel, settings, main-thread pump
└── Dialogs/, icons/
tests/  test_providers.py · test_agent.py · test_static.py · mock_server.py · wait_and_install.sh
tools/  build.py · gen_icons.py
```

## Limitations

- Agent mode (tools) is implemented for OpenAI-compatible providers; Anthropic/Codex run
  as plain chat without tools.
- **LibreOffice 24.2 (Windows)**: if the extension is “silent” after installation (the
  menu is there, clicks do nothing) — make sure the **Python Scripting Support**
  component is installed (enabled by default in the standard installer; reinstall LO
  with it) and update LibreOffice: 24.2 reached end of life in May 2024, the extension
  is tested on 26.8. The extension's Python code runs on the bundled Python — without
  it the assistant does not start and does not report errors.
- In LibreOffice **flatpak** the remote URP bridge is unstable — a quirk of the build;
  the extension works in-process and is unaffected.
- Impress/Draw are supported in the basic scenario (reading/inserting shape text);
  Calc-level tools for them are planned.
- Windows and macOS: installation is supported but has not yet been verified on real
  machines (issue reports are welcome).

## License

MIT — see [LICENSE](LICENSE).
