# Git LFS in Databricks Git folders

A small, self-contained demo of **Git Large File Storage (LFS)** in Databricks Git folders with
**Git CLI access** (Public Preview).

Standard Git folders can't handle LFS. Git folders with Git CLI access run real `git` and
`git lfs` on serverless compute, so LFS-tracked data, models, and images check out with their
real content and can be committed and pushed from a notebook or the web terminal.

## What's in the repo

| Path | Size | Stored as |
|---|---|---|
| `data/transactions.parquet` | ~60 MB, 3M synthetic card transactions | **Git LFS** |
| `models/fraud_model_v1.npz` | Logistic regression weights | **Git LFS** |
| `assets/fraud_rate_by_category.png` | Chart | **Git LFS** |
| `data/transactions_sample.csv` | 1,000-row sample | Regular Git blob, for comparison |
| `.gitattributes` | LFS tracking rules | Regular Git |
| `notebooks/01_git_lfs_demo.py` | The demo notebook | Regular Git |
| `scripts/generate_assets.py` | Regenerates the LFS assets locally | Regular Git |

All data is synthetic.

## Prerequisites

1. A workspace admin enables **Git CLI support for Git folders** on the **Previews** page.
2. Serverless compute is enabled, and serverless can reach `github.com`.
3. You have a GitHub credential in **Settings → Linked accounts** (a PAT with `repo` scope or the
   GitHub app) that can read and write this repo.
4. **Classic compute (DBR 17.0+) only:** classic DBR doesn't include `git-lfs`. Attach
   `scripts/install_git_lfs_init.sh` as a cluster init script *before* cloning, so clones download
   LFS content. Without it, the notebook installs `git-lfs` for its own session and runs
   `git lfs pull` to replace pointer files, but the web terminal won't have LFS.

## Run the demo

### Option A: clone from the web terminal

1. Open any notebook attached to serverless compute and launch the **web terminal**
   (the terminal icon in the right-hand side panel).
2. Clone the repo into your user folder. Repos cloned from the web terminal always get Git CLI
   access:

   ```bash
   cd /Workspace/Users/<your-email>/
   git clone https://github.com/dpandey-db/gitcli-demo.git
   cd gitcli-demo
   git lfs ls-files --size     # LFS objects are already downloaded
   ls -lh data/                # transactions.parquet is the real ~60 MB file
   git cat-file -p HEAD:data/transactions.parquet   # ...but Git only stores a pointer
   ```

### Option B: create the Git folder from the UI

**Workspace → Create → Git folder**, paste the repo URL, and create it. If the workspace is
eligible, the folder gets Git CLI access automatically.

### Walk through the notebook

Open `notebooks/01_git_lfs_demo`, attach **serverless** compute (environment version 5 or
above), and run it top to bottom. The notebook:

1. Checks `git` / `git lfs` and the repo state.
2. Lists the LFS-tracked files and their patterns.
3. Compares the ~130-byte LFS pointer in Git with the 60 MB file in the working tree.
4. Reads the Parquet file with Pandas, scores it with the LFS-stored model, and shows the image.
5. Makes a pointer-only clone (`GIT_LFS_SKIP_SMUDGE=1`) and runs a selective
   `git lfs pull --include="models/*"`.
6. Trains a v2 model, writes a new Parquet file, and commits and pushes both as LFS objects to a
   new `lfs-demo/...` branch.

Then open the branch on GitHub: the new files show **Stored with Git LFS**.

## Talking points

- **Pointers in Git, content in LFS.** Clones and history stay small, and binary files don't
  bloat the `.git` directory.
- **Transparent to code.** Once checked out, Pandas, Spark, NumPy, and `open()` read the real
  bytes. Nothing is LFS-specific.
- **Automatic tracking.** New files that match `.gitattributes` become LFS objects on `git add`.
- **Selective download.** `GIT_LFS_SKIP_SMUDGE=1` plus `git lfs pull --include` fetches only
  what a job needs.
- **Beyond GitHub's file limit.** GitHub rejects regular files over 100 MB. With LFS you can
  push files up to your plan's LFS file-size limit.
- **Same credentials.** The Git CLI uses your workspace Git credential. If you have more than one
  for a provider, set `DB_GIT_CREDENTIAL_NAME`.

## Track new file types

```bash
git lfs track "*.onnx"          # adds a rule to .gitattributes
git add .gitattributes model.onnx
git commit -m "Track ONNX models with LFS"
git push
```

To move files that are already committed into LFS (this rewrites history):
`git lfs migrate import --include="*.csv" --everything`.

## Regenerate the assets locally

```bash
git lfs install
uv run scripts/generate_assets.py
```
