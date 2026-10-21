# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas", "pyarrow"]
# ///
"""Generate the large demo file that is tracked with Git LFS.

Run from the repo root:
    uv run scripts/generate_assets.py

Output:
    data/transactions.parquet  (~60 MB, LFS)
"""

from pathlib import Path

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


def main() -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    df = make_transactions(np.random.default_rng(SEED))
    df.to_parquet(ROOT / "data/transactions.parquet", index=False, compression="snappy")
    print(f"rows={len(df):,} fraud_rate={df['is_fraud'].mean():.4%}")


if __name__ == "__main__":
    main()
