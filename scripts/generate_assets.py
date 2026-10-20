# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib"]
# ///
"""Generate the large, binary demo assets that are tracked with Git LFS.

Run from the repo root:
    uv run scripts/generate_assets.py

Outputs:
    data/transactions.parquet        (~50 MB, LFS)
    data/transactions_sample.csv     (small, regular Git blob)
    models/fraud_model_v1.npz        (LFS)
    assets/fraud_rate_by_category.png (LFS)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
N_ROWS = 3_000_000
SEED = 42

CATEGORIES = np.array(
    ["grocery", "fuel", "travel", "electronics", "dining", "online", "atm", "pharmacy"]
)
CHANNELS = np.array(["pos", "online", "mobile", "branch"])
PROVINCES = np.array(["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"])


def make_transactions(rng: np.random.Generator) -> pd.DataFrame:
    amount = np.round(rng.lognormal(mean=3.5, sigma=1.1, size=N_ROWS), 2)
    category = rng.choice(CATEGORIES, size=N_ROWS)
    channel = rng.choice(CHANNELS, size=N_ROWS, p=[0.45, 0.30, 0.20, 0.05])
    hour = rng.integers(0, 24, size=N_ROWS)
    is_foreign = rng.random(N_ROWS) < 0.06

    # Synthetic fraud signal: large, foreign, late-night, online/electronics/travel.
    logit = (
        -6.0
        + 0.9 * np.log1p(amount) / 3
        + 1.6 * is_foreign
        + 0.8 * ((hour <= 4) | (hour >= 23))
        + 0.7 * np.isin(category, ["electronics", "travel", "online"])
        + 0.5 * (channel == "online")
    )
    is_fraud = rng.random(N_ROWS) < 1 / (1 + np.exp(-logit))

    return pd.DataFrame(
        {
            "transaction_id": np.arange(1, N_ROWS + 1, dtype=np.int64),
            "customer_id": rng.integers(100_000, 999_999, size=N_ROWS),
            "ts": pd.Timestamp("2026-01-01")
            + pd.to_timedelta(rng.integers(0, 365 * 24 * 3600, size=N_ROWS), unit="s"),
            "amount": amount,
            "category": category,
            "channel": channel,
            "province": rng.choice(PROVINCES, size=N_ROWS),
            "hour": hour.astype(np.int8),
            "is_foreign": is_foreign,
            "is_fraud": is_fraud,
        }
    )


def featurize(df: pd.DataFrame) -> np.ndarray:
    """Feature vector shared with the notebook's scoring code."""
    return np.column_stack(
        [
            np.ones(len(df)),
            np.log1p(df["amount"].to_numpy()),
            df["is_foreign"].to_numpy(dtype=float),
            ((df["hour"] <= 4) | (df["hour"] >= 23)).to_numpy(dtype=float),
            df["category"].isin(["electronics", "travel", "online"]).to_numpy(dtype=float),
            (df["channel"] == "online").to_numpy(dtype=float),
        ]
    )


def train_logreg(X: np.ndarray, y: np.ndarray, iters: int = 15) -> np.ndarray:
    """Tiny Newton-method logistic regression (numpy only)."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        hessian = (X * (p * (1 - p))[:, None]).T @ X
        w -= np.linalg.solve(hessian, X.T @ (p - y))
    return w


def main() -> None:
    rng = np.random.default_rng(SEED)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "assets").mkdir(exist_ok=True)

    df = make_transactions(rng)
    df.to_parquet(ROOT / "data/transactions.parquet", index=False, compression="snappy")
    df.head(1_000).to_csv(ROOT / "data/transactions_sample.csv", index=False)

    train = df.sample(500_000, random_state=SEED)
    w = train_logreg(featurize(train), train["is_fraud"].to_numpy(dtype=float))
    np.savez(
        ROOT / "models/fraud_model_v1.npz",
        weights=w,
        feature_names=np.array(
            ["bias", "log_amount", "is_foreign", "late_night", "risky_category", "online"]
        ),
        version=np.array("v1"),
    )

    rate = df.groupby("category")["is_fraud"].mean().sort_values() * 100
    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
    ax.barh(rate.index, rate.values, color="#1b6fa8")
    ax.set_xlabel("Fraud rate (%)")
    ax.set_title("Synthetic fraud rate by merchant category")
    fig.tight_layout()
    fig.savefig(ROOT / "assets/fraud_rate_by_category.png")

    print(f"rows={len(df):,} fraud_rate={df['is_fraud'].mean():.4%} weights={np.round(w, 3)}")


if __name__ == "__main__":
    main()
