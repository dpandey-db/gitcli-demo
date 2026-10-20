# Git LFS in Databricks Git folders

A small demo of copying a large file stored with **Git Large File Storage (LFS)** from a
Databricks Git folder with **Git CLI access** (Public Preview) to a workspace folder and a Unity
Catalog volume.

## What's in the repo

| Path | Size | Stored as |
|---|---|---|
| `data/transactions.parquet` | ~60 MB, 3M synthetic card transactions | **Git LFS** |
| `models/fraud_model_v1.npz`, `assets/fraud_rate_by_category.png` | Small extra binaries | **Git LFS** |
| `data/transactions_sample.csv` | 1,000-row sample | Regular Git, for comparison |
| `.gitattributes` | LFS tracking rules | Regular Git |
| `notebooks/01_git_lfs_demo.py` | The demo notebook | Regular Git |
| `scripts/install_git_lfs_init.sh` | Cluster init script that installs `git-lfs` on classic DBR | Regular Git |
| `scripts/generate_assets.py` | Regenerates the LFS assets locally | Regular Git |

All data is synthetic.

## Prerequisites

1. A workspace admin enables **Git CLI support for Git folders** on the **Previews** page.
2. Serverless compute is enabled, and serverless can reach `github.com`.
3. You have a GitHub credential in **Settings → Linked accounts** that can read this repo.
4. `WRITE VOLUME` on the target volume (set in the notebook's `volume_dir` widget).
5. **Classic compute (DBR 17.0+) only:** classic DBR includes `git` but not `git-lfs`. The notebook
   installs it for its own session if it's missing. For the web terminal and other notebooks on
   the cluster, attach `scripts/install_git_lfs_init.sh` as a cluster init script.

## Run the demo

1. Create a Git folder for this repo: **Workspace → Create → Git folder**, then paste the repo URL.
2. Open `notebooks/01_git_lfs_demo`, attach serverless compute (environment version 5 or above)
   or a DBR 17.0+ cluster, set the widgets, and run it top to bottom. The notebook:
   1. Makes sure `git-lfs` is available and runs `git lfs pull` for the file. A new Git folder may
      contain only LFS pointer files until you do this.
   2. Checks that the file's size and SHA-256 match the LFS pointer, which proves it's the real content.
   3. Copies it to a workspace folder and the volume, and checks each copy the same way.
   4. Reads the copy from the volume with Spark.

## Talking points

- **Pointers in Git, content in LFS.** Git stores a ~130-byte pointer (SHA-256 and size). The
  content lives in the LFS store and is downloaded with `git lfs pull`.
- **Download only what you need.** `git lfs pull --include=<path>` fetches a single file.
- **Beyond GitHub's file limit.** GitHub rejects regular files over 100 MB. With LFS you can push
  files up to your plan's LFS file-size limit.
- **Same credentials.** The Git CLI uses your workspace Git credential. If you have more than one
  for a provider, set `DB_GIT_CREDENTIAL_NAME`.

## Pushing LFS files

`git push` uploads LFS content through Git LFS's `pre-push` hook. If your machine sets a global
`core.hooksPath` (for example, to company-wide hooks), that hook doesn't run and only the pointers
are pushed. Upload the content explicitly and check that it worked:

```bash
git lfs push --all origin
```

## Regenerate the assets locally

```bash
git lfs install
uv run scripts/generate_assets.py
```
