"""Catalogue of ready-to-use provider presets.

Every OpenAI-compatible service only needs a base URL swap; Anthropic and
OpenAI Responses (Codex) have their own API styles.
"""

PRESETS = {
    # --- Z.ai (GLM) ------------------------------------------------------
    "zai-coding": {
        "label": "Z.ai Coding Plan (GLM)",
        "api_style": "openai",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "models": ["glm-4.7", "glm-4.6", "glm-4.5-air", "glm-4.5-flash"],
        "key_url": "https://z.ai/manage-apikey/apikey-list",
        "note": "Subscription key (from ~$3/mo). Use this endpoint, not the "
                "open-platform one, with a Coding Plan key.",
    },
    "zai-open": {
        "label": "Z.ai Open Platform (GLM)",
        "api_style": "openai",
        "base_url": "https://api.z.ai/api/paas/v4",
        "models": ["glm-4.7", "glm-4.6", "glm-4.5-air", "glm-4.5-flash", "glm-4.5v"],
        "key_url": "https://z.ai/manage-apikey/apikey-list",
        "note": "Pay-per-token billing.",
    },
    # --- Anthropic ---------------------------------------------------------
    "anthropic": {
        "label": "Anthropic Claude",
        "api_style": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
        "key_url": "https://console.anthropic.com/settings/keys",
        "note": "Model names are editable; check docs.anthropic.com for the "
                "current list.",
    },
    # --- OpenAI ------------------------------------------------------------
    "openai": {
        "label": "OpenAI (GPT)",
        "api_style": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o", "gpt-4o-mini"],
        "key_url": "https://platform.openai.com/api-keys",
        "note": "Chat Completions API.",
    },
    "openai-codex": {
        "label": "OpenAI (Codex)",
        "api_style": "responses",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-5.1-codex-max",
            "gpt-5.1-codex",
            "gpt-5-codex",
            "codex-mini-latest",
        ],
        "key_url": "https://platform.openai.com/api-keys",
        "note": "Codex models use the Responses API (handled automatically).",
    },
    # --- OpenAI-compatible clouds -------------------------------------------
    "gemini": {
        "label": "Google Gemini",
        "api_style": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-3-pro-preview", "gemini-3-flash", "gemini-2.5-pro",
                   "gemini-2.5-flash"],
        "key_url": "https://aistudio.google.com/apikey",
        "note": "OpenAI-compatible endpoint of the Gemini API.",
    },
    "openrouter": {
        "label": "OpenRouter (400+ models)",
        "api_style": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openrouter/auto", "z-ai/glm-4.6", "anthropic/claude-sonnet-4.5",
                   "openai/gpt-5.1", "deepseek/deepseek-chat"],
        "key_url": "https://openrouter.ai/keys",
        "note": "One key, almost every model. Slug list: openrouter.ai/models.",
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_style": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "key_url": "https://platform.deepseek.com/api_keys",
    },
    "mistral": {
        "label": "Mistral AI",
        "api_style": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-large-latest", "mistral-medium-latest",
                   "mistral-small-latest", "magistral-medium-latest"],
        "key_url": "https://console.mistral.ai/api-keys",
    },
    "groq": {
        "label": "Groq (fast Llama/Qwen/GPT-OSS)",
        "api_style": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "openai/gpt-oss-120b",
                   "openai/gpt-oss-20b", "qwen/qwen3-32b"],
        "key_url": "https://console.groq.com/keys",
    },
    "xai": {
        "label": "xAI (Grok)",
        "api_style": "openai",
        "base_url": "https://api.x.ai/v1",
        "models": ["grok-4", "grok-3", "grok-code-fast-1"],
        "key_url": "https://console.x.ai",
    },
    "together": {
        "label": "Together AI",
        "api_style": "openai",
        "base_url": "https://api.together.xyz/v1",
        "models": ["Qwen/Qwen3-235B-A22B-fp8-tt", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"],
        "key_url": "https://api.together.ai/settings/api-keys",
    },
    "fireworks": {
        "label": "Fireworks AI",
        "api_style": "openai",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "models": ["accounts/fireworks/models/kimi-k2-instruct",
                   "accounts/fireworks/models/llama4-maverick-instruct-basic"],
        "key_url": "https://fireworks.ai/account/api-keys",
    },
    "perplexity": {
        "label": "Perplexity (online search)",
        "api_style": "openai",
        "base_url": "https://api.perplexity.ai",
        "models": ["sonar", "sonar-pro"],
        "key_url": "https://www.perplexity.ai/settings/api",
        "note": "Sonar models fetch fresh web sources.",
    },
    # --- Local ---------------------------------------------------------------
    "ollama": {
        "label": "Ollama (local)",
        "api_style": "openai",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.1", "qwen2.5", "gemma3"],
        "key_url": "https://ollama.com/library",
        "note": "No API key needed. Models: whatever you pulled, e.g. `ollama pull qwen2.5`.",
    },
    "lmstudio": {
        "label": "LM Studio (local)",
        "api_style": "openai",
        "base_url": "http://localhost:1234/v1",
        "models": ["local-model"],
        "key_url": "https://lmstudio.ai",
        "note": "Start the LM Studio server; model name is shown there.",
    },
    # --- Generic ---------------------------------------------------------------
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "api_style": "openai",
        "base_url": "",
        "models": [],
        "key_url": "",
        "note": "Any vLLM, LiteLLM, AI gateway or self-hosted endpoint.",
    },
}

PRESET_ORDER = [
    "zai-coding", "zai-open", "anthropic", "openai", "openai-codex",
    "gemini", "openrouter", "deepseek", "mistral", "groq", "xai",
    "together", "fireworks", "perplexity", "ollama", "lmstudio", "custom",
]


def get_preset(pid):
    return PRESETS.get(pid) or PRESETS["custom"]


def preset_labels():
    return [(pid, PRESETS[pid]["label"]) for pid in PRESET_ORDER if pid in PRESETS]
