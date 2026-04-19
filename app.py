import difflib
import streamlit as st

from prompts import BASE_PROMPT_V1
from agent import run_agent
from evaluator import evaluate
from optimizer import optimize_prompt
from memory_store import log_run, read_last_runs, summarize_failures



st.set_page_config(page_title="PromptForge | Team CODEX", layout="wide")

st.markdown(
    """
    <style>
    .pf-card {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 16px;
        padding: 14px 16px;
        background: white;
        box-shadow: 0 1px 8px rgba(0,0,0,0.05);
    }
    .pf-kpi {
        font-size: 28px;
        font-weight: 800;
        margin: 0;
        line-height: 1.0;
    }
    .pf-label {
        font-size: 12px;
        opacity: 0.7;
        margin-top: 6px;
    }
    .pf-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        border: 1px solid rgba(0,0,0,0.12);
        background: rgba(0,0,0,0.03);
        margin-right: 6px;
    }
    .pf-up { background: rgba(0, 255, 0, 0.08); border-color: rgba(0, 140, 0, 0.25); }
    .pf-down { background: rgba(255, 0, 0, 0.08); border-color: rgba(140, 0, 0, 0.25); }
    .pf-neutral { background: rgba(0, 0, 0, 0.03); }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("PromptForge — Self-Improving Agentic AI")
st.caption("Team CODEX | PS-12: Evaluate → Detect failures → Modify prompt/workflow → Improve safely")


# Session state

if "prompt" not in st.session_state:
    st.session_state.prompt = BASE_PROMPT_V1
if "best_score" not in st.session_state:
    st.session_state.best_score = 0.0

# Sidebar controls

with st.sidebar:
    st.header("Controls")
    target_score = st.slider("Target score", 0.70, 1.00, 0.95, 0.01)
    max_versions = st.selectbox("Max versions", [2, 3, 4], index=2)  # default 4
    demo_mode = st.toggle("Demo mode (faster)", value=False)
    show_prompt_panel = st.toggle("Show prompt + diff", value=True)
    show_memory_panel = st.toggle("Show memory panel", value=True)

    st.divider()
    #st.write("**Tip for judges:** keep target at **0.90–0.95**. Score 1.00 is unrealistic for local models.")

# Demo mode reduces LLM calls
# - Demo mode: do only v1 and v2
if demo_mode:
    max_versions = 2

# Input + top KPI row

colA, colB = st.columns([1.35, 0.65])

with colA:
    question = st.text_area(
        "Task / Prompt (can be coding, math, general — the system adapts)",
        value="",
        height=110
    )

with colB:
    # KPI cards
    k1, k2 = st.columns(2)
    with k1:
        st.markdown(
            f"""
            <div class="pf-card">
              <p class="pf-kpi">{st.session_state.best_score:.2f}</p>
              <div class="pf-label">Best score so far</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with k2:
        st.markdown(
            f"""
            <div class="pf-card">
              <p class="pf-kpi">{target_score:.2f}</p>
              <div class="pf-label">Target score</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.divider()

# Optional memory panel

if show_memory_panel:
    runs = read_last_runs(20)
    fail_counts = summarize_failures(runs) if runs else {}
    top_row = st.columns([1, 1, 1])
    with top_row[0]:
        st.markdown('<span class="pf-badge pf-neutral">Memory</span>', unsafe_allow_html=True)
        st.write("Recent runs stored for pattern detection.")
    with top_row[1]:
        st.markdown('<span class="pf-badge pf-neutral">Top failure patterns</span>', unsafe_allow_html=True)
        st.json(fail_counts if fail_counts else {})
    with top_row[2]:
        st.markdown('<span class="pf-badge pf-neutral">Safety</span>', unsafe_allow_html=True)
        st.write("We only continue iterations when the score strictly increases.")
    st.divider()

# Core monotonic loop 

def run_one(prompt_text: str):
    ans = run_agent(question, prompt_text)
    ev = evaluate(question, ans)
    score = float(ev.get("score", 0.0))
    return ans, ev, score

def make_diff(old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="prompt_before",
        tofile="prompt_after",
        lineterm=""
    )
    return "\n".join(diff)

run_btn = st.button("Run Self-Improvement (v1 → vN)", type="primary")

if run_btn:
    with st.spinner("Running self-improvement loop..."):
        history = []
        prompt = st.session_state.prompt

        # v1
        ans1, ev1, s1 = run_one(prompt)
        history.append({
            "v": "v1",
            "prompt": prompt,
            "answer": ans1,
            "ev": ev1,
            "score": s1,
            "changes": [],
            "diff": ""
        })

        # early stop
        if s1 >= target_score:
            final_prompt = prompt
        else:
            final_prompt = prompt

            prev_score = s1
            prev_prompt = prompt

            # v2..vN
            for i in range(2, max_versions + 1):
                opt = optimize_prompt(prev_prompt, ev1.get("failure_tags", []), ev1.get("one_sentence_reason", ""))
                cand_prompt = opt.get("new_prompt", prev_prompt)
                changes = opt.get("changes", [])
                diff_txt = make_diff(prev_prompt, cand_prompt)

                ans, ev, score = run_one(cand_prompt)

                # monotonic policy: continue only if improves
                improved = score > prev_score

                history.append({
                    "v": f"v{i}",
                    "prompt": cand_prompt,
                    "answer": ans,
                    "ev": ev,
                    "score": score,
                    "changes": changes,
                    "diff": diff_txt,
                    "improved": improved
                })

                if not improved:
                    # stop (do not accept worse)
                    final_prompt = prev_prompt
                    break

                # accept
                prev_score = score
                prev_prompt = cand_prompt
                ev1 = ev  # next optimization uses latest failures
                final_prompt = cand_prompt

                if score >= target_score:
                    break

        # best score tracking
        best_item = max(history, key=lambda x: x["score"])
        st.session_state.best_score = max(st.session_state.best_score, best_item["score"])
        st.session_state.prompt = final_prompt

        # log proof
        log_run({
            "question": question,
            "target_score": float(target_score),
            "max_versions": int(max_versions),
            "demo_mode": bool(demo_mode),
            "history": [
                {
                    "version": h["v"],
                    "score": float(h["score"]),
                    "failure_tags": h["ev"].get("failure_tags", []),
                    "reason": h["ev"].get("one_sentence_reason", ""),
                    "changes": h.get("changes", []),
                    "improved": h.get("improved", True)
                } for h in history
            ],
            "best_score": float(best_item["score"])
        })

    # Result summary row

    scores = [h["score"] for h in history]
    status = "Target reached" if best_item["score"] >= target_score else "Stopped (no improvement or max versions)"

    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.markdown(f'<div class="pf-card"><p class="pf-kpi">{len(history)}</p><div class="pf-label">Versions generated</div></div>', unsafe_allow_html=True)
    with s_col2:
        st.markdown(f'<div class="pf-card"><p class="pf-kpi">{scores[0]:.2f}</p><div class="pf-label">v1 score</div></div>', unsafe_allow_html=True)
    with s_col3:
        st.markdown(f'<div class="pf-card"><p class="pf-kpi">{best_item["score"]:.2f}</p><div class="pf-label">Best score this run</div></div>', unsafe_allow_html=True)
    with s_col4:
        st.markdown(f'<div class="pf-card"><p class="pf-kpi">{status}</p><div class="pf-label">Run status</div></div>', unsafe_allow_html=True)

    st.divider()


    # Score trend chart

    st.subheader("Score trend (evidence)")
    chart_data = {h["v"]: h["score"] for h in history}
    st.line_chart(chart_data)

    st.divider()

    # Tabs per version (clean browsing)

    st.subheader("Versions (clean view)")
    tabs = st.tabs([h["v"] for h in history])

    for tab, h in zip(tabs, history):
        with tab:
            v = h["v"]
            score = h["score"]
            tags = h["ev"].get("failure_tags", [])
            reason = h["ev"].get("one_sentence_reason", "")

            # Delta badge
            idx = [x["v"] for x in history].index(v)
            delta_html = ""
            if idx == 0:
                delta_html = '<span class="pf-badge pf-neutral">baseline</span>'
            else:
                prev = history[idx - 1]["score"]
                if score > prev:
                    delta_html = f'<span class="pf-badge pf-up">↑ +{(score-prev):.2f}</span>'
                elif score < prev:
                    delta_html = f'<span class="pf-badge pf-down">↓ {(score-prev):.2f}</span>'
                else:
                    delta_html = '<span class="pf-badge pf-neutral">no change</span>'

            st.markdown(delta_html, unsafe_allow_html=True)

            c1, c2 = st.columns([1, 2])

            with c1:
                st.markdown("**Score**")
                st.metric(label="", value=f"{score:.2f}")
                st.markdown("**Failure tags**")
                st.write(tags)
                st.markdown("**Reason**")
                st.write(reason if reason else "-")

                if h.get("changes"):
                    st.markdown("**Prompt changes**")
                    st.write(h["changes"])

            with c2:
                st.markdown("**Answer**")
                st.write(h["answer"])

            if show_prompt_panel:
                st.divider()
                st.markdown("**Prompt used**")
                st.code(h["prompt"], language="text")
                if h.get("diff"):
                    st.markdown("**Prompt diff vs previous**")
                    st.code(h["diff"], language="diff")

    st.divider()
    st.subheader("Final Prompt Kept (current active)")
    st.code(st.session_state.prompt, language="text")
    st.caption(f"Best score so far (session): {st.session_state.best_score:.2f}")
else:
    st.info("Click **Run Self-Improvement** to generate v1→vN, view score trend, and inspect prompt diffs.")


