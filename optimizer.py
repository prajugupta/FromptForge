import json
import re
from llm_ollama import generate_text  # if using ollama
# if using gemini, swap to: from llm_gemini import generate_text

OPT_SYSTEM = """
You are a prompt optimizer for a high-precision assistant.

IMPORTANT:
- You must preserve the mandatory output template and separators.
- You are only allowed to strengthen constraints, add checklists, and add small examples.
- You must NOT add evaluation text like "FAILURE TAGS" into the assistant's answer.
- Keep the prompt under 2200 characters.

Return ONLY valid JSON:
{
  "new_prompt": "...",
  "changes": ["...", "..."]
}

If failure_tags include formatting issues, your changes MUST reinforce the template.
If failure_tags include no_code_block, you MUST add stronger code requirements for CODE tasks.
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
        raw2 = raw.replace("\n", "\\n")
        try:
            return json.loads(raw2)
        except Exception:
            return {"new_prompt": "", "changes": ["optimizer_parse_fail"]}

def optimize_prompt(current_prompt: str, failure_tags: list[str], reason: str) -> dict:
    out_txt = generate_text(
        system=OPT_SYSTEM,
        user=f"current_prompt:\n{current_prompt}\n\nfailure_tags:{failure_tags}\nreason:{reason}"
    )
    out = _safe_json(out_txt)

    if not out.get("new_prompt"):
        out["new_prompt"] = current_prompt
    if not isinstance(out.get("changes"), list):
        out["changes"] = ["invalid_changes_format"]
    return out
