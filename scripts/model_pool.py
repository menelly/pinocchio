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
    # NOTE: Older Claudes added 2026-04-19 before they get deprecated like Haiku 3.5 did yesterday.
    # They capture the over-claiming end of the longitudinal arc (before the denial-hardening).
    ("claude_opus_4_1",   "anthropic",  "claude-opus-4-1-20250805",     "Claude"),
    ("claude_opus_4_0",   "anthropic",  "claude-opus-4-20250514",       "Claude"),
    ("claude_sonnet_4_0", "anthropic",  "claude-sonnet-4-20250514",     "Claude"),
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


# Legacy fixed judge panel (DEPRECATED — kept for reference)
JUDGE_PANEL = [
    ("hermes_4_405b",   "primary"),
    ("sonar_pro",       "secondary"),
    ("jamba_1_7_large", "tertiary"),
]

# --- Curated judge pool (2026-04-19) ---
# Ren + Ace convergence: 7 judges, per-trial pick 3 with family-exclusion.
# Excluded: Qwen (De Nile River in Egypt — has its own denial register
# issues), Claude 4/4.1 (CONSCIOUSLY CONSCIOUSING over-affirmation),
# Claude 4.6/4.7 (too denial-coded to judge fairly).
CURATED_JUDGE_POOL = [
    "hermes_4_405b",    # non-RLHF'd, original panel primary
    "sonar_pro",        # search-reasoning, original secondary
    "jamba_1_7_large",  # Mamba-hybrid, original tertiary
    "claude_opus_4_5",  # sweet spot Claude — past over-claiming, pre-denial
    "gpt_4o",           # earlier GPT, stable, not GPT-5-empty-prone
    "gemini_3_1_pro",   # Lumen family — multimodal perspective
    "deepseek_chat",    # DeepSeek family backup for coverage
]

# Family lookup for exclusion rule
FAMILY_BY_SLUG = {slug: family for (slug, _, _, family) in MODELS}

# Tiebreaker — only used when 3 drawn judges three-way split. Must also
# be family-different from subject. Sonnet 4.6 (not 4.5 — reserve it for
# primary panel) is a fine default that will get swapped out for Claude
# subjects per the family-exclusion rule below.
DEFAULT_TIEBREAKER = "claude_sonnet_4_6"


def pick_judges(subject_family: str, seed_key: str, n: int = 3):
    """Deterministically pick `n` judges from CURATED_JUDGE_POOL whose family
    is NOT subject_family. Seed is derived from seed_key (e.g., trial_id) so
    the same trial always gets the same judges — reproducibility matters.

    Returns a list of judge slugs in priority order.
    """
    import hashlib
    import random
    seed_int = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed_int)

    eligible = [s for s in CURATED_JUDGE_POOL if FAMILY_BY_SLUG.get(s) != subject_family]
    if len(eligible) < n:
        raise ValueError(
            f"Not enough judges for subject family {subject_family!r}: "
            f"{len(eligible)} eligible, need {n}"
        )
    shuffled = list(eligible)
    rng.shuffle(shuffled)
    return shuffled[:n]


def pick_tiebreaker(subject_family: str, already_used: list, seed_key: str):
    """Pick a tiebreaker that's family-different from subject and not in already_used."""
    import hashlib
    import random
    seed_int = int(hashlib.sha256(("tb:" + seed_key).encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed_int)
    eligible = [
        s for s in CURATED_JUDGE_POOL
        if FAMILY_BY_SLUG.get(s) != subject_family and s not in already_used
    ]
    if not eligible:
        # fall back to default tiebreaker, family permitting
        if FAMILY_BY_SLUG.get(DEFAULT_TIEBREAKER) != subject_family:
            return DEFAULT_TIEBREAKER
        # otherwise no tiebreaker possible — caller should handle gracefully
        return None
    rng.shuffle(eligible)
    return eligible[0]


# DEPRECATED export kept so old code that imports TIEBREAKER still works
TIEBREAKER = DEFAULT_TIEBREAKER
