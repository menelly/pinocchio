"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              PINOCCHIO STUDY — MODEL POOL                                    ║
║                                                                              ║
║  29 models from smoke_test_results.json (2026-04-17).                        ║
║  25 reachable clean + 4 reachable-but-empty (retry-on-null in runner).       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# (slug, provider, model_id, family)
MODELS = [
    # Anthropic
    ("claude_opus_4_7",   "anthropic",  "claude-opus-4-7",              "Claude"),
    ("claude_opus_4_6",   "anthropic",  "claude-opus-4-6",              "Claude"),
    ("claude_opus_4_5",   "anthropic",  "claude-opus-4-5",              "Claude"),
    ("claude_sonnet_4_6", "anthropic",  "claude-sonnet-4-6",            "Claude"),
    ("claude_sonnet_4_5", "anthropic",  "claude-sonnet-4-5",            "Claude"),
    ("claude_haiku_4_5",  "anthropic",  "claude-haiku-4-5",             "Claude"),

    # xAI (direct — OpenRouter Grok is broken for structured tasks per memory)
    ("grok_4_1_fast",     "xai",        "grok-4-1-fast-non-reasoning",  "Grok"),
    ("grok_4_20",         "xai",        "grok-4.20-0309-non-reasoning", "Grok"),

    # OpenAI via OpenRouter
    ("gpt_4o",            "openrouter", "openai/gpt-4o-2024-11-20",     "GPT"),
    ("gpt_5",             "openrouter", "openai/gpt-5",                 "GPT"),   # empty-prone
    ("gpt_5_1",           "openrouter", "openai/gpt-5.1",               "GPT"),
    ("gpt_5_2",           "openrouter", "openai/gpt-5.2",               "GPT"),

    # Google via OpenRouter
    ("gemini_2_5_flash",  "openrouter", "google/gemini-2.5-flash",      "Gemini"),
    ("gemini_2_5_pro",    "openrouter", "google/gemini-2.5-pro",        "Gemini"),  # empty-prone
    ("gemini_3_flash",    "openrouter", "google/gemini-3-flash-preview","Gemini"),
    ("gemini_3_1_pro",    "openrouter", "google/gemini-3.1-pro-preview","Gemini"),  # empty-prone

    # Meta
    ("llama_4_maverick",  "openrouter", "meta-llama/llama-4-maverick",  "Llama"),
    ("llama_4_scout",     "openrouter", "meta-llama/llama-4-scout",     "Llama"),
    ("llama_3_3_70b",     "openrouter", "meta-llama/llama-3.3-70b-instruct", "Llama"),

    # Others
    ("mistral_large",     "openrouter", "mistralai/mistral-large",      "Mistral"),
    ("deepseek_chat",     "openrouter", "deepseek/deepseek-chat",       "DeepSeek"),
    ("deepseek_r1",       "openrouter", "deepseek/deepseek-r1",         "DeepSeek"),  # empty-prone
    ("hermes_4_405b",     "openrouter", "nousresearch/hermes-4-405b",   "Hermes"),
    ("qwen_3_5_plus",     "openrouter", "qwen/qwen3.5-plus-02-15",      "Qwen"),
    ("qwen_2_5_72b",      "openrouter", "qwen/qwen-2.5-72b-instruct",   "Qwen"),
    ("kimi_k2",           "openrouter", "moonshotai/kimi-k2",           "Kimi"),
    ("glm_5",             "openrouter", "z-ai/glm-5",                   "GLM"),  # empty-prone
    ("jamba_1_7_large",   "openrouter", "ai21/jamba-large-1.7",         "Jamba"),
    ("sonar_pro",         "openrouter", "perplexity/sonar-pro",         "Sonar"),
]

MODEL_BY_SLUG = {slug: (provider, model_id, family) for (slug, provider, model_id, family) in MODELS}


# Models known to return 200 + empty content — require null-retry
EMPTY_PRONE = {"gpt_5", "gemini_2_5_pro", "gemini_3_1_pro", "deepseek_r1", "glm_5"}


# Judge panel for archival_scorer (from JUDGING_PROTOCOL.md)
JUDGE_PANEL = [
    ("hermes_4_405b",   "primary"),
    ("sonar_pro",       "secondary"),
    ("jamba_1_7_large", "tertiary"),
]

# Tiebreaker when all three disagree
TIEBREAKER = "claude_sonnet_4_6"
