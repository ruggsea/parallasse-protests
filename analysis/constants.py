"""Every selection number of the study, in one place. PLAN.md carries the same block; analysis/check_plan.py compares them."""
import gzip, os
def opn(p, mode="rt"):
    """open a data file, falling back to p + .gz (the three large files are shipped gzipped)"""
    if not os.path.exists(p) and os.path.exists(p + ".gz"): p += ".gz"
    return gzip.open(p, mode) if p.endswith(".gz") else open(p, mode)

WINDOW = ("2026-09-25", "2026-10-25")
GATE1_CHARS = 1500          # prefilter.py: title + first N chars searched for a protest term
LABEL_CHARS = 1500          # relevance_label.py: title + first N chars given to the model
PAYWALL_MIN_CHARS = 1500    # mark_paywall.py: stored text shorter than this is paywall_truncated
FRAMING_SET = "protest==1 and youth==1 (relevance_qwen.jsonl + relevance_qwen2.jsonl)"
SERVED_WINDOW = 65536       # tokens, vLLM max_model_len of both engines
MAX_TOKENS = {"A": 900, "B": 3000}   # A = Qwen3.8-27B, B = gpt-oss-120b (reasoning tokens count)
TEMPERATURE = 0
MODELS = {"A": "Qwen/Qwen3.8-27B (BF16, port 18767)", "B": "openai/gpt-oss-120b (MXFP4 as released, port 18766)"}
CLAUDE_SAMPLE = {"italian": 200, "other": 100, "seed": 20261030}
KAPPA_SAMPLE = {"italian": 300, "other": 300, "seed": 20261031}
MIN_BODY_CHARS = 200        # shorter text gets no body call (empty scrapes); the title-only call still runs
LIVE_BLOG_CHARS = 30000     # longer text is flagged live_blog in the analysis, not removed
DUP_HEAD_CHARS = 600         # same-outlet articles with identical first N characters get no body call
