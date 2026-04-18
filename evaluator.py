import json
import re
from llm_ollama import generate_text  # ✅ using Ollama

EVAL_SYSTEM = """
You are a strict evaluator. Return ONLY valid JSON, nothing else.

Evaluate the assistant output against the required format and task type.

Return JSON exactly like this:
{
  "score": 0.0,
  "rubric": {
    "correctness": 0.0,
    "completeness": 0.0,
    "clarity": 0.0,
    "formatting": 0.0
  },
  "task_type_detected": "CODE|MATH|GENERAL|OTHER",
  "failure_tags": ["..."],
  "one_sentence_reason": "..."
}

Allowed failure tags:
- bad_format
- missing_task_type
- missing_short_answer
- missing_steps
- missing_final_output
- no_code_block
- wrong_task_type
- incorrect_or_confusing
- too_verbose
- too_short
""".strip()


def _extract_json(text: str) -> str | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else None


def _clean_control_chars(s: str) -> str:
    s = s.replace("\t", " ").replace("\r", "")
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return s


def _safe_json(text: str) -> dict:
    raw = _extract_json(text) or ""
    raw = _clean_control_chars(raw)
    try:
        return json.loads(raw)
    except Exception:
        # fallback: convert literal newlines to \\n
        raw2 = raw.replace("\n", "\\n")
        try:
            return json.loads(raw2)
        except Exception:
            return {
                "score": 0.0,
                "rubric": {"correctness": 0.0, "completeness": 0.0, "clarity": 0.0, "formatting": 0.0},
                "task_type_detected": "OTHER",
                "failure_tags": ["judge_parse_fail"],
                "one_sentence_reason": "Evaluator JSON could not be parsed."
            }


def _rule_tags(answer: str) -> list[str]:
    tags = []

    # Must include the template sections
    if "Task Type:" not in answer:
        tags.append("missing_task_type")
    if "Short Answer:" not in answer:
        tags.append("missing_short_answer")
    if "Step-by-step:" not in answer:
        tags.append("missing_steps")
    if "Final Output:" not in answer:
        tags.append("missing_final_output")

    # Must include decorative separators (keeps it “attractive”)
    if "────────────────" not in answer:
        tags.append("bad_format")

    # Detect task type from output
    m = re.search(r"Task Type:\s*(CODE|MATH|GENERAL|OTHER)", answer)
    task_type = m.group(1) if m else "OTHER"

    # If CODE: must include code block
    if task_type == "CODE" and "```" not in answer:
        tags.append("no_code_block")

    # Length checks
    if len(answer) < 120:
        tags.append("too_short")
    if len(answer) > 3200:
        tags.append("too_verbose")

    return tags


def evaluate(question: str, answer: str) -> dict:
    txt = generate_text(
        system=EVAL_SYSTEM,
        user=f"QUESTION:\n{question}\n\nASSISTANT_ANSWER:\n{answer}"
    )
    ev = _safe_json(txt)

    tags = set(ev.get("failure_tags", []))
    tags.update(_rule_tags(answer))

    score = float(ev.get("score", 0.0))

    # Deterministic penalties for format violations
    penalty = 0.0
    if "bad_format" in tags: penalty += 0.10
    if "missing_task_type" in tags: penalty += 0.10
    if "missing_short_answer" in tags: penalty += 0.06
    if "missing_steps" in tags: penalty += 0.08
    if "missing_final_output" in tags: penalty += 0.08
    if "no_code_block" in tags: penalty += 0.12
    if "too_short" in tags: penalty += 0.05
    if "too_verbose" in tags: penalty += 0.03

    score = max(0.0, min(1.0, score - penalty))

    # Guarantee fields
    ev.setdefault("rubric", {"correctness": 0.0, "completeness": 0.0, "clarity": 0.0, "formatting": 0.0})
    ev.setdefault("task_type_detected", "OTHER")
    ev.setdefault("one_sentence_reason", "Evaluation complete.")
    ev["score"] = score
    ev["failure_tags"] = sorted(tags)

    return ev