"""Keep recorded file declarations separate from generator configuration."""
from collections import Counter


def declared_summary(caller, files):
    pairs = Counter((entry.get("vendor"), entry.get("model")) for entry in files.values())
    known = sorted(pairs, key=lambda pair: (str(pair[0]), str(pair[1])))
    single = known[0] if len(known) == 1 else (None, None)
    return {
        "vendor": single[0],
        "model": single[1],
        "declared_file_models": [
            {"vendor": vendor, "model": model, "files": pairs[(vendor, model)]}
            for vendor, model in known
        ],
        "attribution": {
            "summary_basis": "recorded per-file declarations",
            "original_provider_use_verified": False,
            "note": "File labels and matching audio hashes do not verify original provider use.",
        },
        "renderer_configuration": {
            "default_vendor": caller.get("vendor"),
            "default_model": caller.get("model"),
            "default_tariff": {key: caller.get(key) for key in (
                "usd_per_1m_input_tokens", "usd_per_1m_audio_output_tokens",
                "price_source", "price_checked")},
            "fallback_voices": caller.get("rime_voices", {}),
        },
    }
