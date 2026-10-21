# Git LFS in Databricks Git folders

A small demo of copying a large file stored with **Git Large File Storage (LFS)** from a
Databricks Git folder with **Git CLI access** (Public Preview) to a workspace folder and a Unity
Catalog volume.

## What's in the repo

| Path | Size | Stored as |
|---|---|---|
| `data/transactions.parquet` | ~60 MB, 3M synthetic card transactions | **Git LFS** |
| `.gitattributes` | LFS tracking rules | Regular Git |
| `notebooks/02_copy_lfs_file_to_volume.py` | The demo notebook | Regular Git |
| `notebooks/01_git_lfs_demo.py` | Extended version with checksum checks and a workspace-folder copy | Regular Git |
| `scripts/generate_assets.py` | Regenerates the Parquet file locally | Regular Git |

All data is synthetic.

## Prerequisites

1. A workspace admin enables **Git CLI support for Git folders** on the **Previews** page.
2. Serverless compute is enabled, and serverless can reach `github.com`.
3. You have a GitHub credential in **Settings → Linked accounts** that can read this repo.
4. `WRITE VOLUME` on the target volume.
5. **Classic compute (DBR 17.0+) only:** classic DBR includes `git` but not `git-lfs`. The notebooks
   download it for their own session if it's missing. Nothing is installed on the cluster.

## Run the demo

1. Create a Git folder for this repo: **Workspace → Create → Git folder**, then paste the repo URL.
2. Open `notebooks/02_copy_lfs_file_to_volume`, attach serverless compute (environment version 5
   or above) or a DBR 17.0+ cluster, change the volume path to one you can write to, and run it
   top to bottom. The notebook:
   1. Downloads Git LFS for the notebook session if the compute doesn't include it.
   2. Turns on Git LFS for the repository and lists the files it tracks.
   3. Runs `git lfs pull` to download the full file. A new Git folder may contain only LFS pointer
      files until you do this.
   4. Copies the Parquet file to the volume and reads it with Spark.

`notebooks/01_git_lfs_demo` does the same, and also checks that each copy's SHA-256 matches the LFS
pointer and copies the file to a workspace folder. Set its widgets before running it.

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
