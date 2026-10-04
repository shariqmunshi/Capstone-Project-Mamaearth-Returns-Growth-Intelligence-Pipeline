"""Part 3: SCR (Situation-Complication-Resolution) narrator.

Reads narrator/findings.json (written by analysis/clean_and_eda.py) and turns the verified
numbers into a business narrative. Online path: Gemini via the google-genai library.
Offline path: a deterministic template, used when no API key is set or the API call fails.

Run from the repo root:   python narrator/generate_narrative.py
Optional (online path):   export GEMINI_API_KEY="your-key"     (Windows: set GEMINI_API_KEY=your-key)
"""
import json
import os
from datetime import datetime

FINDINGS_PATH = "narrator/findings.json"
SAMPLE_PATH = "narrator/sample_output.txt"
# Gemini model names change over time. If GEMINI_MODEL is set it is used alone; otherwise these
# current Flash models are tried in order until one works with your free key.
CANDIDATE_MODELS = ["gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash"]
MODELS = [os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else CANDIDATE_MODELS
MODEL_USED = None  # set to the model that actually answered

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a business narrative of about 250 words using the SCR structure, with exactly three "
    "labeled sections in this order: 'Situation', 'Complication', 'Resolution'. "
    "STRICT RULE: every number in your output must come from the findings supplied by the user "
    "and must appear with exactly the same value. Do not invent, estimate, round differently, "
    "or add any statistic that is not in the findings. Quote rupee amounts and percentages as given."
)


# ----------------------------------------------------------------- helpers
def _inr(x):
    return f"Rs {x:,.2f}"


def _month_name(ym):
    return datetime.strptime(ym, "%Y-%m").strftime("%B")


def build_user_prompt(findings: dict) -> str:
    """Every number is interpolated from `findings`; nothing is hardcoded here."""
    f = findings
    rates = ", ".join(f"{k} {v}%" for k, v in f["return_rate_by_payment"].items())
    seg = f["highest_risk_segment"]
    peak = f["true_peak_month"]
    inf = f["outlier_inflated_month"]
    return (
        "Write the SCR narrative from these verified findings:\n"
        f"- Cleaned total revenue: {_inr(f['cleaned_total_revenue_inr'])}\n"
        f"- Raw total revenue before cleaning: {_inr(f['raw_total_revenue_inr'])}\n"
        f"- Difference caused by removing duplicate double-submitted orders: "
        f"{_inr(f['duplicate_reconciliation_delta_inr'])}\n"
        f"- Return rate by payment method: {rates}\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities, "
        f"return rate {seg['return_rate_pct']}%\n"
        f"- True peak revenue month: {_month_name(peak['month'])} ({peak['month']}), "
        f"{_inr(peak['revenue_inr'])}\n"
        f"- {_month_name(inf['month'])} ({inf['month']}) looked highest at "
        f"{_inr(inf['apparent_revenue_inr'])} but is {_inr(inf['corrected_revenue_inr'])} after "
        f"excluding two bulk orders\n"
        "Use only these figures."
    )


# ------------------------------------------------------------ offline path
def generate_scr_narrative_offline(findings: dict) -> dict:
    """Deterministic template: no network, no key. Same return shape as the online path."""
    f = findings
    r = f["return_rate_by_payment"]
    seg = f["highest_risk_segment"]
    peak = f["true_peak_month"]
    inf = f["outlier_inflated_month"]
    narrative = (
        "SITUATION\n"
        f"After cleaning the order data, Mamaearth's total revenue stands at "
        f"{_inr(f['cleaned_total_revenue_inr'])}. The raw figure of {_inr(f['raw_total_revenue_inr'])} "
        f"was overstated by {_inr(f['duplicate_reconciliation_delta_inr'])}, which comes entirely from "
        f"duplicate double-submitted orders that have been removed. "
        f"{_month_name(peak['month'])} is the genuine peak month at {_inr(peak['revenue_inr'])}.\n\n"
        "COMPLICATION\n"
        f"Returns are concentrated by payment method: COD returns run at {r['COD']}%, against "
        f"{r['CARD']}% for CARD and {r['UPI']}% for UPI. The problem is sharpest in one segment: "
        f"{seg['payment_method']} orders in Tier-{seg['city_tier']} cities return at "
        f"{seg['return_rate_pct']}%. Separately, {_month_name(inf['month'])} appeared to be the "
        f"best month at {_inr(inf['apparent_revenue_inr'])}, but that was an artifact of two bulk "
        f"orders; corrected, it is {_inr(inf['corrected_revenue_inr'])}.\n\n"
        "RESOLUTION\n"
        f"Ops should prioritise {seg['payment_method']} in Tier-{seg['city_tier']} cities "
        f"({seg['return_rate_pct']}% returns) for intervention, such as order confirmation calls or "
        f"nudging buyers toward prepaid payment. Finance should plan against the cleaned total of "
        f"{_inr(f['cleaned_total_revenue_inr'])} and treat {_month_name(peak['month'])} "
        f"({_inr(peak['revenue_inr'])}) as the true peak when forecasting."
    )
    return {"status": "success", "narrative": narrative, "tokens": None}


# ------------------------------------------------------------- online path
def _call_gemini(findings: dict, api_key: str) -> dict:
    """Gemini call, trying each candidate model in turn. Always returns a dict; never raises."""
    global MODEL_USED
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,  # role + structure + number rule, not in the prompt
            # temperature 0.0: this is a factual business report, not creative writing, so we want
            # the most deterministic, least embellished output the model can give.
            temperature=0.0,
            # Explicit limit. Generous because some Gemini models spend part of this budget on
            # internal "thinking"; the visible 3-section ~250-word narrative needs far less.
            max_output_tokens=8192,
            http_options=types.HttpOptions(timeout=60000),  # milliseconds = 60 s (minimum is 10 s)
        )
        prompt = build_user_prompt(findings)
        last_err = None
        for model in MODELS:
            try:
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                if not response.text:
                    raise RuntimeError("Gemini returned no text (blocked or empty response)")
                MODEL_USED = model
                return {
                    "status": "success",
                    "narrative": response.text,
                    "tokens": response.usage_metadata.total_token_count,
                }
            except Exception as err:  # try the next model
                last_err = f"{model}: {err}"
        raise RuntimeError(f"all models failed; last error -> {last_err}")
    except Exception as err:  # caller must never receive a raw exception
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative(findings: dict) -> dict:
    """Online first (if GEMINI_API_KEY is set), falling back to the offline template."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[narrator] No GEMINI_API_KEY set -> using offline template.")
        return generate_scr_narrative_offline(findings)
    result = _call_gemini(findings, api_key)
    if result["status"] == "error":
        print(f"[narrator] Gemini call failed ({result['message'][:300]}) -> using offline template.")
        return generate_scr_narrative_offline(findings)
    print(f"[narrator] Gemini narrative generated with model {MODEL_USED}.")
    return result


# ----------------------------------------------------------------- checker
def _fmt(x, places):
    return f"{x:.{places}f}".rstrip("0").rstrip(".") if places else f"{x}"


def check_narrative(narrative: str, findings: dict) -> bool:
    """Asserts all five required figures appear (commas removed first). Prints PASS/FAIL per figure."""
    text = narrative.replace(",", "")
    peak = findings["true_peak_month"]
    required = {
        "cleaned total revenue": _fmt(findings["cleaned_total_revenue_inr"], 2),
        "COD return rate": _fmt(findings["return_rate_by_payment"]["COD"], 1),
        "COD + Tier-2 segment rate": _fmt(findings["highest_risk_segment"]["return_rate_pct"], 1),
        "duplicate reconciliation delta": _fmt(findings["duplicate_reconciliation_delta_inr"], 2),
        "peak month name": _month_name(peak["month"]),
        "peak month revenue": _fmt(peak["revenue_inr"], 2),
    }
    all_ok = True
    for label, needle in required.items():
        ok = needle in text
        all_ok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: looking for '{needle}'")
    print("  RESULT:", "ALL FIGURES PRESENT" if all_ok else "SOME FIGURES MISSING")
    return all_ok


# -------------------------------------------------------------------- main
if __name__ == "__main__":
    with open(FINDINGS_PATH) as fh:
        findings = json.load(fh)

    result = generate_scr_narrative(findings)
    print("\n" + result["narrative"] + "\n")

    online = result["tokens"] is not None
    if online:
        with open(SAMPLE_PATH, "w") as fh:
            fh.write(result["narrative"])
        print(f"Saved the live Gemini output to {SAMPLE_PATH} (tokens used: {result['tokens']}).")
        print(f"Checking saved sample ({SAMPLE_PATH}):")
        with open(SAMPLE_PATH) as fh:
            check_narrative(fh.read(), findings)
    else:
        print("Checking offline narrative:")
        assert check_narrative(result["narrative"], findings), "offline template is missing a figure"
        print("(No live Gemini output this run, so narrator/sample_output.txt was not written.)")
