"""Model selection for generated studies; no downloads or inference."""

DEFAULT_MODELS = ("qwen3:4b", "gemma3:4b")


def select_models(models=None, *, pair=False):
    selected = DEFAULT_MODELS if models is None else models
    if not isinstance(selected, (list, tuple)) or not selected:
        raise ValueError("Provide a nonempty list of model names")
    if any(not isinstance(m, str) or not m.strip() or m != m.strip()
           or any(c.isspace() for c in m) or m.startswith("script:") for m in selected):
        raise ValueError("Use exact installed model names, without whitespace or script: prefixes")
    if pair and len(selected) != 2:
        raise ValueError("The game study needs exactly two player models; repeat a name for self-play")
    if not pair and len(set(selected)) != len(selected):
        raise ValueError("Duplicate model names would duplicate study cases")
    return list(selected)


def case_models(config):
    """Actual participants, including legacy configurations without a models field."""
    return sorted({case["model"] for case in config["cases"]})
