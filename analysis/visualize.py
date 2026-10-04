"""Part 2, Task 11: two Matplotlib charts, rebuilt from the raw CSVs every run.
Run from the repo root (after or independent of clean_and_eda.py):  python analysis/visualize.py
The cleaning steps repeat clean_and_eda.py so this script is fully re-runnable on its own."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

os.makedirs("visualizations", exist_ok=True)

# ---- same cleaning as clean_and_eda.py ----
orders = pd.read_csv("data/orders.csv")
products = pd.read_csv("data/products.csv")
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
key = ["customer_id", "product_id", "order_date", "quantity",
       "discount_pct", "payment_method", "rating", "returned"]
orders = orders[~orders.duplicated(subset=key, keep="first")].copy()
orders["discount_pct"] = orders["discount_pct"].fillna(0)
orders["rating"] = orders["rating"].fillna(orders["rating"].median())
df = orders.merge(products, on="product_id", how="left")
df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100)
q1, q3 = df["quantity"].quantile(0.25), df["quantity"].quantile(0.75)
iqr = q3 - q1
df["is_outlier"] = (df["quantity"] < q1 - 1.5 * iqr) | (df["quantity"] > q3 + 1.5 * iqr)

# ---- Chart 1: return rate by payment method (descending, labeled) ----
rate = (df.groupby("payment_method")["returned"].mean() * 100).round(1).sort_values(ascending=False)
top, bottom = rate.index[0], rate.index[-1]
fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(rate.index, rate.values, color=["#c0392b", "#7f8c8d", "#95a5a6"])
for b, v in zip(bars, rate.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}%", ha="center", fontweight="bold")
card = rate["CARD"]
ax.set_title(f"{top} Returns at {rate[top]:.1f}% - {rate[top] / card:.0f}x Card")
ax.set_xlabel("Payment method")
ax.set_ylabel("Return rate (%)")
ax.set_ylim(0, rate.max() + 8)
fig.tight_layout()
fig.savefig("visualizations/return_rate_by_payment.png", dpi=150)
plt.close(fig)

# ---- Chart 2: outlier-corrected monthly revenue ----
df["order_date"] = pd.to_datetime(df["order_date"])
df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
monthly = df[~df["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
peak = monthly.idxmax()
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(monthly.index, monthly.values, marker="o", color="#2c7fb8")
ax.annotate(f"Peak: {monthly[peak]:,.2f}", (peak, monthly[peak]),
            textcoords="offset points", xytext=(0, 10), ha="center")
ax.set_title(f"Outlier-Corrected Monthly Revenue - Peak in {peak}")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (Rs)")
ax.set_ylim(0, monthly.max() * 1.15)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig("visualizations/monthly_revenue_trend.png", dpi=150)
plt.close(fig)

print("Saved visualizations/return_rate_by_payment.png")
print("Saved visualizations/monthly_revenue_trend.png")
print("Return rates:", rate.to_dict())
print("Monthly corrected revenue:", monthly.to_dict())
