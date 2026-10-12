"""Privacy-preserving usage ledger. No prices are inferred or model calls made.

Only token counts explicitly supplied by a model API are called metered.
Missing or implausible usage is recorded as unknown, never as zero cost.
"""
from datetime import datetime, timezone
from luna import core

MAX_REPORTED_TOKENS = 100_000_000


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS model_usage_events (
        id INTEGER PRIMARY KEY,
        provider TEXT NOT NULL, model TEXT NOT NULL,
        mode TEXT NOT NULL, prompt_tokens INTEGER,
        completion_tokens INTEGER, total_tokens INTEGER,
        metered INTEGER NOT NULL,
        created_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS model_usage_day_idx "
               "ON model_usage_events(created_at,id)")


def _token(value):
    return (value if type(value) is int and 0 <= value <= MAX_REPORTED_TOKENS
            else None)


def _usage(response_data, adapter):
    """Extract provider-reported usage metadata, not estimates."""
    if not isinstance(response_data, dict):
        return None, None, None, False
    if adapter == "gemini":
        raw = response_data.get("usageMetadata")
        keys = ("promptTokenCount", "candidatesTokenCount", "totalTokenCount")
    elif adapter == "openai_compatible":
        raw = response_data.get("usage")
        keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    else:
        return None, None, None, False
    if not isinstance(raw, dict):
        return None, None, None, False
    values = tuple(_token(raw.get(key)) for key in keys)
    # A partial/invalid response cannot be represented as a verified total.
    valid = all(v is not None for v in values)
    if valid and values[2] < max(values[0], values[1]):
        valid = False
    return (*values, valid) if valid else (None, None, None, False)


def record(provider, model, mode, response_data, adapter):
    if (not isinstance(provider, str) or not 1 <= len(provider) <= 120
            or not isinstance(model, str) or not 1 <= len(model) <= 120
            or mode not in ("local", "cloud")
            or adapter not in ("gemini", "openai_compatible")):
        raise ValueError("Invalid usage metadata")
    prompt, completion, total, metered = _usage(response_data, adapter)
    with core.connect() as db:
        _setup(db)
        cur = db.execute(
            "INSERT INTO model_usage_events(provider,model,mode,prompt_tokens,"
            "completion_tokens,total_tokens,metered,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (provider, model, mode, prompt, completion, total,
             int(metered), core.timestamp()),
        )
        return {"id": cur.lastrowid, "metered": metered,
                "total_tokens": total, "price_known": False}


def report(limit=100):
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        _setup(db)
        recent = db.execute(
            "SELECT provider,model,mode,prompt_tokens,completion_tokens,"
            "total_tokens,metered,created_at FROM model_usage_events "
            "ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    counted = [row for row in recent if row[6]]
    return {
        "events_sampled": len(recent),
        "usage_reported_events": len(counted),
        "unmetered_events": len(recent) - len(counted),
        "reported_prompt_tokens": sum(row[3] for row in counted),
        "reported_completion_tokens": sum(row[4] for row in counted),
        "reported_total_tokens": sum(row[5] for row in counted),
        "dollar_cost": None,
        "cost_accuracy": "unknown: no verified provider prices",
        "scope": "most recent {} recorded successful responses".format(limit),
        "no_prompts_or_api_keys_logged": True,
        "read_only": True,
    }
