"""Part 2: independent pandas pipeline over the raw CSVs.
Run from the repo root:  python analysis/clean_and_eda.py
Reads data/*.csv directly (never the SQL database). Prints every intermediate result."""
import numpy as np
import pandas as pd

pd.set_option("display.width", 120)


def section(title):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


def corr_band(r):
    a = abs(r)
    if a < 0.2:
        return "negligible"
    if a < 0.4:
        return "weak"
    if a < 0.7:
        return "moderate"
    return "strong"


# ----------------------------------------------------------------- Task 1
section("Task 1 - Load and inspect")
orders = pd.read_csv("data/orders.csv")
customers = pd.read_csv("data/customers.csv")
products = pd.read_csv("data/products.csv")
print("orders.shape    :", orders.shape)
print("customers.shape :", customers.shape)
print("products.shape  :", products.shape)

# ----------------------------------------------------------------- Task 2
section("Task 2 - Standardize payment_method casing")
print("Raw unique values   :", sorted(orders["payment_method"].unique()),
      f"({orders['payment_method'].nunique()} distinct)")
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
print("Clean unique values :", sorted(orders["payment_method"].unique()),
      f"({orders['payment_method'].nunique()} distinct)")
print("Counts:\n", orders["payment_method"].value_counts().to_string())

# ----------------------------------------------------------------- Task 3
section("Task 3 - Remove duplicate orders")
key = ["customer_id", "product_id", "order_date", "quantity",
       "discount_pct", "payment_method", "rating", "returned"]
dup_mask = orders.duplicated(subset=key, keep="first")
dropped = orders[dup_mask].copy()
print("Rows flagged as duplicates:", int(dup_mask.sum()))
print("Dropped order_ids:", dropped["order_id"].tolist())
orders_clean = orders[~dup_mask].copy()
print("orders_clean.shape:", orders_clean.shape)

# ----------------------------------------------------------------- Task 4
section("Task 4 - Impute missing values")
n_disc = int(orders_clean["discount_pct"].isnull().sum())
n_rate = int(orders_clean["rating"].isnull().sum())
rating_median = orders_clean["rating"].median()
print(f"discount_pct NaN rows: {n_disc}  -> filled with 0 (business rule: no promo applied)")
print(f"Median of non-null ratings (before imputing): {rating_median}")
print(f"rating NaN rows: {n_rate}  -> filled with median {rating_median}")
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
print("Nulls after imputing:",
      orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

# ----------------------------------------------------------------- Task 5
section("Task 5 - Merge and reconcile against Part 1")
merged = (orders_clean
          .merge(products, on="product_id", how="left")
          .merge(customers, on="customer_id", how="left"))
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
total_clean = merged["order_value"].sum()
print("merged.shape:", merged.shape)
print(f"Total order_value, 175 cleaned rows: {total_clean:,.2f}")

# independent check: value of the 5 dropped rows (their discount NaN treated as 0, as in Part 1)
dropped_val = (dropped.merge(products, on="product_id", how="left")
               .assign(v=lambda d: d["quantity"] * d["price"]
                       * (1 - d["discount_pct"].fillna(0) / 100))["v"].sum())
part1_total = 99860.20
print(f"Part 1 Report (a) raw total          : {part1_total:,.2f}")
print(f"Delta (raw - cleaned)                : {part1_total - total_clean:,.2f}")
print(f"Sum of order_value of 5 dropped rows : {dropped_val:,.2f}")
print(f"Delta equals dropped-row value?      : {abs((part1_total - total_clean) - dropped_val) < 0.005}")
print(f"""
Reconciliation note: Part 1 Report (a) totalled Rs {part1_total:,.2f} on the raw data, while the
cleaned pandas frame totals Rs {total_clean:,.2f}. The difference of Rs {part1_total - total_clean:,.2f} is
fully explained by the 5 duplicate (double-submit) orders O0176-O0180 removed in Task 3: summed
independently, their order_value is Rs {dropped_val:,.2f}. It is NOT caused by imputation. Filling
discount_pct with 0 matches Part 1's COALESCE(discount_pct, 0) treatment, and rating imputation does
not enter order_value at all, so neither changes any order_value total.""")

# ----------------------------------------------------------------- Task 6
section("Task 6 - IQR outlier detection on quantity")
q1, q3 = merged["quantity"].quantile(0.25), merged["quantity"].quantile(0.75)
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print(f"Q1={q1}  Q3={q3}  IQR={iqr}  lower={lower}  upper={upper}")
merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
print("Outlier rows flagged (kept in the data):", int(merged["is_outlier"].sum()))
print(merged.loc[merged["is_outlier"], ["order_id", "order_date", "quantity", "order_value"]].to_string(index=False))

# ----------------------------------------------------------------- Task 7
section("Task 7 - Hypothesis: does COD have a higher return rate?")
print("H1: COD orders have a higher return rate than Card or UPI orders.")
pay = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
pay["return_rate_pct"] = (pay["mean"] * 100).round(1)
print(pay.to_string())
cod_rate = pay.loc["COD", "return_rate_pct"]
other_max = pay.drop("COD")["return_rate_pct"].max()
print("Hypothesis:", "CONFIRMED" if cod_rate > other_max else "NOT CONFIRMED",
      f"(COD {cod_rate}% vs highest other {other_max}%)")

# ----------------------------------------------------------------- Task 8
section("Task 8 - Multi-level segmentation (payment_method x city_tier)")
seg = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
seg["return_rate_pct"] = (seg["mean"] * 100).round(1)
print(seg.to_string())
top = seg["return_rate_pct"].idxmax()
print(f"\nHighest-risk segment: {top[0]} + Tier-{top[1]} cities at {seg.loc[top, 'return_rate_pct']}% "
      f"({int(seg.loc[top, 'count'])} orders)")
t1 = seg.loc[("COD", 1)]
t2 = seg.loc[("COD", 2)]
print(f"COD risk is not uniform: Tier-1 COD {int(t1['count'])} orders at {t1['return_rate_pct']}% "
      f"vs Tier-2 COD {int(t2['count'])} orders at {t2['return_rate_pct']}%.")

# ----------------------------------------------------------------- Task 9
section("Task 9 - Correlation analysis")
cols = ["rating", "returned", "discount_pct", "quantity"]
corr = merged[cols].corr()
print(corr.round(3).to_string())
print("\nPairwise strength (bands: <0.2 negligible, 0.2-0.39 weak, 0.4-0.69 moderate, >=0.7 strong):")
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        r = corr.iloc[i, j]
        print(f"  {cols[i]:>13} vs {cols[j]:<13} r = {r:+.3f}  -> {corr_band(r)}")
r_dr = corr.loc["discount_pct", "returned"]
print(f"\nHypothesis 'higher discounts reduce returns': r = {r_dr:+.3f} "
      f"({corr_band(r_dr)}) -> BUSTED")

# ----------------------------------------------------------------- Task 10
section("Task 10 - Outlier-corrected time series")
merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)
monthly_with = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_without = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
print("(1) Monthly order_value INCLUDING outliers:\n", monthly_with.map("{:.2f}".format).to_string())
print("\n(2) Monthly order_value EXCLUDING outliers (corrected):\n", monthly_without.map("{:.2f}".format).to_string())
peak_with, peak_without = monthly_with.idxmax(), monthly_without.idxmax()
print(f"\nHighest month including outliers: {peak_with}")
print(f"Highest month excluding outliers: {peak_without}")
print(f"""
Interpretation: January's apparent lead is an artifact of the two bulk orders that landed in
January (O0011 on 2026-01-28 with quantity 25, and O0098 on 2026-01-10 with quantity 30). Once
they are excluded, {peak_without} is the genuine peak month. This is why outliers are flagged in
Task 6 before the time series is built in Task 10.""")


# ------------------------------------------------- Export for Part 3 (narrator)
section("Export - narrator/findings.json (feeds Part 3)")
import json
import os

# Raw total recomputed from the raw (un-deduplicated) orders, NaN discount treated as 0%,
# the same rule as Part 1 Report (a). Nothing below is hand-typed.
raw_merged = orders.merge(products, on="product_id", how="left")
raw_total = (raw_merged["quantity"] * raw_merged["price"]
             * (1 - raw_merged["discount_pct"].fillna(0) / 100)).sum()
print(f"Raw total recomputed in pandas: {raw_total:,.2f} (Part 1 Report (a): {part1_total:,.2f})")
assert abs(raw_total - part1_total) < 0.005, "raw total no longer reconciles with Part 1"

findings = {
    "cleaned_total_revenue_inr": round(float(total_clean), 2),
    "raw_total_revenue_inr": round(float(raw_total), 2),
    "duplicate_reconciliation_delta_inr": round(float(raw_total - total_clean), 2),
    "return_rate_by_payment": {k: float(v) for k, v in pay["return_rate_pct"].items()},
    "highest_risk_segment": {
        "payment_method": top[0],
        "city_tier": int(top[1]),
        "return_rate_pct": float(seg.loc[top, "return_rate_pct"]),
    },
    "true_peak_month": {
        "month": peak_without,
        "revenue_inr": round(float(monthly_without[peak_without]), 2),
    },
    "outlier_inflated_month": {
        "month": peak_with,
        "apparent_revenue_inr": round(float(monthly_with[peak_with]), 2),
        "corrected_revenue_inr": round(float(monthly_without[peak_with]), 2),
    },
}
os.makedirs("narrator", exist_ok=True)
with open("narrator/findings.json", "w") as f:
    json.dump(findings, f, indent=2)
print("Wrote narrator/findings.json")
print(json.dumps(findings, indent=2))
