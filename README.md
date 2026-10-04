# Mamaearth Returns & Growth Intelligence Pipeline

An end-to-end pipeline that finds and quantifies where returns are eating into margins:

1. **SQL layer** - a relational store (SQLite) and reporting queries.
2. **Python analysis layer** - pandas cleaning, EDA, charts. It writes the verified numbers to `narrator/findings.json`.
3. **GenAI narrative layer** - turns `findings.json` into a Situation-Complication-Resolution narrative (Gemini, with a keyless offline fallback).

No layer reports a number it did not compute or receive from the layer before it.

## Repo structure

```
<repo>/
├── README.md
├── sql/
│   ├── schema.sql              CREATE TABLE statements (customers, products, orders)
│   ├── seed_data.sql           INSERTs generated from data/*.csv (raw, uncleaned; blanks -> NULL)
│   ├── reports.sql             Reports (a)-(i), actual output pasted above each query
│   ├── make_seed.py            (extra) regenerates seed_data.sql from the CSVs
│   └── run_sql.py              (extra) builds returns.db and runs everything, no SQLite install needed
├── data/
│   ├── customers.csv           committed exactly as given, never edited
│   ├── products.csv
│   └── orders.csv
├── analysis/
│   ├── clean_and_eda.py        Part 2: cleaning and EDA; ends by writing narrator/findings.json
│   └── visualize.py            Part 2: the two charts
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json           written by analysis/clean_and_eda.py (never hand-typed)
    ├── generate_narrative.py   SCR narrator (Gemini online path + offline fallback) and number checker
    └── sample_output.txt       saved live Gemini output, checked by the same checker (required by Part 3)
```

Files marked "(extra)" are helpers that are not part of the required tree; `sample_output.txt` is required by Part 3, Task 5.

## Setup

Python 3.9+ is required. Get the repo and install the libraries:

```
git clone https://github.com/shariqmunshi/Capstone-Project-Mamaearth-Returns-Growth-Intelligence-Pipeline--Mohammed-Shariq-Munshi.git
cd Capstone-Project-Mamaearth-Returns-Growth-Intelligence-Pipeline--Mohammed-Shariq-Munshi
pip install pandas matplotlib google-genai
```

Run every command below from the **repo root** (the folder containing `data/`). In Google Colab, use
`!git clone <url>` and `%cd <folder name>` instead of `cd`, and put `!` in front of each command.

## Run order (and how data flows between layers)

```
data/*.csv --> [1] SQL layer --> sql/reports.sql output (raw totals, e.g. 99,860.20)
data/*.csv --> [2] analysis  --> narrator/findings.json --> [3] narrator --> SCR narrative
```

Part 2 reads the same raw CSVs directly (not the database), so Parts 1 and 2 can run in either order.
The only hand-off between layers is `narrator/findings.json`.

### 1. SQL layer

Using the SQLite command line:
```
sqlite3 returns.db < sql/schema.sql
sqlite3 returns.db < sql/seed_data.sql
sqlite3 returns.db < sql/reports.sql
```
No SQLite command line (for example in Colab)? This does the same with Python's built-in sqlite3 and
regenerates `seed_data.sql`:
```
python sql/run_sql.py
```
Check: `SELECT COUNT(*)` gives 45 customers, 16 products, 180 orders. Report (a) gives
180 orders, total revenue 99,860.20, average order value 554.78.

### 2. Analysis layer
```
python analysis/clean_and_eda.py
python analysis/visualize.py
```
`clean_and_eda.py` prints every intermediate result for Tasks 1-10. **Its final step (the Export section)
writes `narrator/findings.json`**, collecting the verified numbers computed above it: the cleaned total and
reconciliation delta from Task 5, the COD return rates and highest-risk segment from Tasks 7-8, and the
outlier-corrected peak month from Task 10. `visualize.py` writes the two PNGs to `visualizations/`.

Reconciliation with Part 1: the cleaned total is 97,358.30 versus Part 1's raw 99,860.20.
The 2,501.90 difference is exactly the order value of the 5 duplicate orders (O0176-O0180) removed in cleaning.

### 3. Narrative layer
Offline (no key, no network, zero configuration):
```
python narrator/generate_narrative.py
```
With Gemini (free key from Google AI Studio, https://aistudio.google.com/apikey):
```
export GEMINI_API_KEY="your-key"        # Mac/Linux
set GEMINI_API_KEY=your-key             # Windows cmd
python narrator/generate_narrative.py
```
In Colab: `import os; os.environ["GEMINI_API_KEY"] = "your-key"` in a cell, then `!python narrator/generate_narrative.py`.

- With a key, the script calls Gemini (tries current Flash models in turn; force one with the `GEMINI_MODEL` environment variable), saves the output to
  `narrator/sample_output.txt`, and runs the checker on the saved text.
- Without a key, or if the API call fails, it automatically uses the deterministic offline template.
- In both cases a checker prints PASS/FAIL for each required figure: 97,358.30; 44.4; 54.5; 2,501.90; March; 20,318.90.

Gemini settings: system instruction separate from the prompt, `temperature=0.0` (factual report),
explicit `max_output_tokens`, a 60-second timeout, and all errors returned as a structured dict.

## Key findings

- COD returns are 44.4% versus 14.7% for Card and 18.9% for UPI.
- The highest-risk segment is COD orders in Tier-2 cities at 54.5% (Tier-1 COD: 37.5%).
- January's apparent revenue lead is an artifact of two bulk orders; March (20,318.90) is the true peak month.
- Discount level and returns show negligible correlation (r = -0.09).
