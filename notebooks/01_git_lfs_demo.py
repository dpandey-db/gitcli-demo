# Databricks notebook source
# MAGIC %md
# MAGIC # Git LFS in Databricks Git folders (Git CLI preview)
# MAGIC
# MAGIC This notebook runs **inside a Git folder that has Git CLI access** and shows that
# MAGIC Git Large File Storage (LFS) works end to end in Databricks:
# MAGIC
# MAGIC | Step | What you'll see |
# MAGIC |---|---|
# MAGIC | 1 | `git` and `git lfs` are available and the folder is a real Git working tree |
# MAGIC | 2 | Which files are tracked by LFS (`.gitattributes`, `git lfs ls-files`) |
# MAGIC | 3 | What Git actually stores for an LFS file: a ~130-byte **pointer** instead of 60 MB |
# MAGIC | 4 | The LFS-tracked Parquet file, model, and image are fully usable from the notebook |
# MAGIC | 5 | A pointer-only clone and a selective `git lfs pull` |
# MAGIC | 6 | Create a new LFS artifact in Databricks, then commit and push it to a branch |
# MAGIC
# MAGIC **Requirements:** serverless compute (environment version 5+) or DBR 17.0+, the
# MAGIC *Git CLI support for Git folders* preview enabled, and a GitHub Git credential configured
# MAGIC in **Settings → Linked accounts**.

# COMMAND ----------

import os
import shlex
import subprocess

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
).stdout.strip()


def sh(cmd: str, cwd: str = REPO, check: bool = True, env: dict | None = None) -> str:
    """Run a shell command, echo it like a terminal, and return its stdout."""
    print(f"$ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    out = (result.stdout + result.stderr).rstrip()
    if out:
        print(out)
    print()
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {cmd}")
    return result.stdout


print("Repo root:", REPO)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Git CLI and Git LFS are available

# COMMAND ----------

sh("git --version")
sh("git lfs version")
sh("git remote -v")
sh("git status --short --branch")
sh("git log --oneline -5")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Which files does LFS manage?
# MAGIC
# MAGIC `.gitattributes` declares the patterns. `git lfs ls-files` lists every file in the
# MAGIC current commit that is stored in LFS, with its size. A `*` after the object ID means the
# MAGIC real content is checked out locally (a `-` would mean only the pointer is present).

# COMMAND ----------

sh("cat .gitattributes")
sh("git lfs ls-files --size")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Pointer vs. content
# MAGIC
# MAGIC The working tree has the real 60 MB Parquet file, but the Git object database only
# MAGIC stores a tiny text pointer containing the SHA-256 and size of the content. Compare
# MAGIC that with the small CSV, which is a normal Git blob.

# COMMAND ----------

sh("ls -lh data/ models/ assets/")

print("---- What Git stores for the LFS-tracked Parquet file ----")
sh("git cat-file -p HEAD:data/transactions.parquet")
sh("git cat-file -s HEAD:data/transactions.parquet  # blob size in bytes")

print("---- What Git stores for the regular CSV file ----")
sh("git cat-file -s HEAD:data/transactions_sample.csv  # blob size in bytes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Use the LFS-tracked files like any other workspace file
# MAGIC
# MAGIC LFS is transparent: once the content is checked out, Pandas, NumPy, and Spark read the
# MAGIC files as usual.

# COMMAND ----------

import numpy as np
import pandas as pd

tx = pd.read_parquet(f"{REPO}/data/transactions.parquet")
print(f"{len(tx):,} rows, {tx.memory_usage(deep=True).sum() / 1e6:,.0f} MB in memory")
display(tx.head(20))

# COMMAND ----------

display(
    tx.groupby("category")
    .agg(transactions=("transaction_id", "count"), fraud_rate=("is_fraud", "mean"), avg_amount=("amount", "mean"))
    .sort_values("fraud_rate", ascending=False)
    .reset_index()
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load the versioned model (also stored in LFS) and score the data

# COMMAND ----------


def featurize(df: pd.DataFrame) -> np.ndarray:
    # Must match scripts/generate_assets.py
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


def lift_at_top(y: np.ndarray, score: np.ndarray, pct: float = 0.01) -> float:
    """Fraud rate in the top `pct` of scores divided by the overall fraud rate."""
    top = np.argsort(-score)[: int(len(score) * pct)]
    return y[top].mean() / y.mean()


model_v1 = np.load(f"{REPO}/models/fraud_model_v1.npz")
w1 = model_v1["weights"]
print("Model version:", model_v1["version"])
display(pd.DataFrame({"feature": model_v1["feature_names"], "weight": w1}))

y = tx["is_fraud"].to_numpy(dtype=float)
score_v1 = 1 / (1 + np.exp(-featurize(tx) @ w1))
print(f"v1 lift in top 1% of scores: {lift_at_top(y, score_v1):.2f}x")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Display the LFS-tracked image

# COMMAND ----------

from IPython.display import Image

Image(filename=f"{REPO}/assets/fraud_rate_by_category.png", width=700)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Pointer-only clone and selective download
# MAGIC
# MAGIC Large repos don't have to download every LFS object. With `GIT_LFS_SKIP_SMUDGE=1`, a clone
# MAGIC checks out only the pointers; `git lfs pull --include` then fetches only what you need.
# MAGIC Here we clone this Git folder into local scratch space to show it.

# COMMAND ----------

SCRATCH = "/tmp/lfs-pointer-clone"
sh(f"rm -rf {SCRATCH}")
sh(f"git clone --quiet file://{REPO} {SCRATCH}", env={"GIT_LFS_SKIP_SMUDGE": "1"})

print("---- After a pointer-only clone: files are tiny pointers ----")
sh("ls -l data/ models/ assets/", cwd=SCRATCH)
sh("cat models/fraud_model_v1.npz", cwd=SCRATCH)
sh("git lfs ls-files", cwd=SCRATCH)

print("---- Pull only the model files ----")
sh('git lfs pull --include="models/*"', cwd=SCRATCH)
sh("ls -l data/ models/", cwd=SCRATCH)
sh("git lfs ls-files", cwd=SCRATCH)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Create a new LFS artifact in Databricks and push it
# MAGIC
# MAGIC We train a **v2** model with one extra feature, write it plus a Parquet file of
# MAGIC high-risk transactions, and commit both on a new branch. Because the paths match the
# MAGIC `.gitattributes` patterns, Git LFS handles them automatically: no extra commands.
# MAGIC
# MAGIC The push uploads the LFS objects to GitHub's LFS store first, then pushes the commit. The
# MAGIC workspace Git credential is used automatically.

# COMMAND ----------

dbutils.widgets.text("branch", "", "Branch to push (blank = auto)")
user = spark.sql("SELECT current_user()").first()[0]
branch = dbutils.widgets.get("branch") or f"lfs-demo/{user.split('@')[0]}-{pd.Timestamp.now():%Y%m%d-%H%M%S}"
print("Branch:", branch)

# Use the workspace user as the commit identity if none is configured.
if not sh("git config user.email", check=False).strip():
    sh(f"git config user.email {shlex.quote(user)}")
    sh(f"git config user.name {shlex.quote(user.split('@')[0])}")

sh(f"git switch -c {shlex.quote(branch)}")

# COMMAND ----------


def featurize_v2(df: pd.DataFrame) -> np.ndarray:
    # v1 features + "amount over $500"
    return np.column_stack([featurize(df), (df["amount"] > 500).to_numpy(dtype=float)])


def train_logreg(X: np.ndarray, y: np.ndarray, iters: int = 15) -> np.ndarray:
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        hessian = (X * (p * (1 - p))[:, None]).T @ X
        w -= np.linalg.solve(hessian, X.T @ (p - y))
    return w


train = tx.sample(500_000, random_state=7)
w2 = train_logreg(featurize_v2(train), train["is_fraud"].to_numpy(dtype=float))
score_v2 = 1 / (1 + np.exp(-featurize_v2(tx) @ w2))
print(f"v1 lift in top 1%: {lift_at_top(y, score_v1):.2f}x")
print(f"v2 lift in top 1%: {lift_at_top(y, score_v2):.2f}x")

np.savez(
    f"{REPO}/models/fraud_model_v2.npz",
    weights=w2,
    feature_names=np.append(model_v1["feature_names"], "amount_gt_500"),
    version=np.array("v2"),
)

high_risk = tx.assign(fraud_score=score_v2).nlargest(250_000, "fraud_score")
high_risk.to_parquet(f"{REPO}/data/high_risk_transactions.parquet", index=False)

sh("ls -lh models/ data/")

# COMMAND ----------

# MAGIC %md
# MAGIC `git lfs status` confirms the new files will be committed as LFS objects (`LFS: <oid>`)
# MAGIC rather than regular Git blobs.

# COMMAND ----------

sh("git add models/fraud_model_v2.npz data/high_risk_transactions.parquet")
sh("git lfs status")
sh('git commit -m "Add v2 fraud model and high-risk transactions (Git LFS, created in Databricks)"')
sh(f"git push -u origin {shlex.quote(branch)}")

# COMMAND ----------

sh("git lfs ls-files --size")
remote = sh("git remote get-url origin").strip().removesuffix(".git")
displayHTML(
    f'Open <a href="{remote}/tree/{branch}/data" target="_blank">{remote}/tree/{branch}/data</a> '
    "and click a Parquet file: GitHub shows <b>Stored with Git LFS</b>."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Clean up (optional)
# MAGIC
# MAGIC Switch the Git folder back to `main` and delete the demo branch locally and on GitHub.

# COMMAND ----------

# sh("git switch main")
# sh(f"git branch -D {shlex.quote(branch)}")
# sh(f"git push origin --delete {shlex.quote(branch)}")
