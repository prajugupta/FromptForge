import json, time
from typing import Any

LOG_FILE = "runs.jsonl"

def log_run(data: dict[str, Any]) -> None:
    data["ts"] = int(time.time())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def read_last_runs(n: int = 20) -> list[dict]:
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        return [json.loads(x) for x in lines]
    except FileNotFoundError:
        return []

def summarize_failures(runs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in runs:
        for item in r.get("history", []):
            for t in item.get("failure_tags", []):
                counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))