import json
from prompts import BASE_PROMPT_V1
from agent import run_agent
from evaluator import evaluate
from optimizer import optimize_prompt
from guardrails import should_rollback

TEST_SET = [
    "Write Python code to check if a string is a palindrome.",
    "Reverse a string in Python using two different methods.",
    "Write Python code to compute factorial (iterative and recursive).",
    "Count vowels in a string in Python.",
    "Remove duplicates from a list while preserving order in Python.",
    "Find the second largest number in a list in Python.",
    "Solve Two Sum: return indices of two numbers that add up to target in Python.",
    "Merge two sorted lists into one sorted list in Python.",
    "Check if a number is prime in Python efficiently.",
    "Print Fibonacci numbers up to N in Python."
]

def avg(xs): return sum(xs) / max(1, len(xs))

def run_suite(prompt: str):
    rows = []
    for q in TEST_SET:
        ans = run_agent(q, prompt)
        ev = evaluate(q, ans)
        rows.append({"question": q, "score": ev["score"], "failure_tags": ev["failure_tags"]})
    return {"avg_score": avg([r["score"] for r in rows]), "rows": rows}

def main():
    prompt = BASE_PROMPT_V1

    baseline = run_suite(prompt)

    # optimize based on one representative hard question
    q = "Solve Two Sum: return indices of two numbers that add up to target in Python."
    ans = run_agent(q, prompt)
    ev = evaluate(q, ans)
    opt = optimize_prompt(prompt, ev["failure_tags"], ev.get("one_sentence_reason", ""))

    improved_prompt = opt["new_prompt"]
    improved = run_suite(improved_prompt)

    rolled_back = should_rollback(baseline["avg_score"], improved["avg_score"])
    final_prompt = prompt if rolled_back else improved_prompt

    out = {
        "baseline_avg": baseline["avg_score"],
        "improved_avg": improved["avg_score"],
        "rolled_back": rolled_back,
        "changes": opt["changes"],
        "final_prompt": final_prompt,
        "baseline": baseline,
        "improved": improved
    }

    with open("results_report.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Baseline avg:", round(out["baseline_avg"], 3))
    print("Improved avg:", round(out["improved_avg"], 3))
    print("Rolled back?:", out["rolled_back"])
    print("Saved: results_report.json")

if __name__ == "__main__":
    main()
