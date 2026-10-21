# Databricks notebook source
# MAGIC %md
# MAGIC # Copy a Git LFS file from a Git folder to workspace files and a volume
# MAGIC
# MAGIC This notebook runs inside a **Git folder with Git CLI access** and shows how to take a large
# MAGIC file stored with Git LFS and copy it to a workspace folder and a Unity Catalog volume.
# MAGIC
# MAGIC 1. Make sure `git-lfs` is available and download the LFS content (`git lfs pull`)
# MAGIC 2. Confirm the file is real content, not an LFS pointer
# MAGIC 3. Copy it to a workspace folder and a volume, and verify each copy's checksum
# MAGIC 4. Read the copy from the volume with Spark
# MAGIC
# MAGIC **Requirements:** the *Git CLI support for Git folders* preview, serverless compute
# MAGIC (environment version 5+) or DBR 17.0+, and `WRITE VOLUME` on the target volume.

# COMMAND ----------

dbutils.widgets.text("lfs_file", "data/transactions.parquet", "LFS file (repo-relative)")
dbutils.widgets.text("workspace_dir", "", "Workspace target dir (blank = ~/lfs_demo_output)")
dbutils.widgets.text("volume_dir", "/Volumes/devanshu_pandey/boc/documents/lfs_demo", "Volume target dir")

# COMMAND ----------

import os
import subprocess


def find_repo_root() -> str:
    """Walk up from this notebook's folder to the Git folder root (the dir containing .git).

    Uses the notebook path rather than the working directory, which differs between
    serverless and classic compute.
    """
    nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    path = os.path.dirname(f"/Workspace{nb_path}")
    while path != "/":
        if os.path.exists(os.path.join(path, ".git")):
            return path
        path = os.path.dirname(path)
    raise RuntimeError(f"No .git found above {nb_path}. Is this notebook in a Git folder with Git CLI access?")


REPO = find_repo_root()

# On classic compute, workspace files can be owned by a different OS user than the notebook
# process, and Git refuses to use them ("dubious ownership"). Trust only this repo, and only
# for git commands launched from this notebook (nothing is written to global Git config).
_check = subprocess.run(["git", "-C", REPO, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
if "dubious ownership" in _check.stderr:
    n = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    os.environ.update({"GIT_CONFIG_COUNT": str(n + 1), f"GIT_CONFIG_KEY_{n}": "safe.directory", f"GIT_CONFIG_VALUE_{n}": REPO})
    _check = subprocess.run(["git", "-C", REPO, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
if _check.returncode != 0:
    raise RuntimeError(f"git can't open {REPO}:\n{_check.stderr}")


def sh(cmd: str, cwd: str = REPO, check: bool = True) -> str:
    """Run a shell command, echo it like a terminal, and return its stdout."""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    out = (result.stdout + result.stderr).rstrip()
    if out:
        print(out)
    print()
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {cmd}")
    return result.stdout


LFS_FILE = dbutils.widgets.get("lfs_file")
SRC = os.path.join(REPO, LFS_FILE)
print("Repo root:", REPO)
print("LFS file: ", SRC)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Make sure Git LFS is available and download the content
# MAGIC
# MAGIC Serverless compute includes `git-lfs`. Classic DBR does not, so if it's missing we download
# MAGIC the official release binary for this notebook session (no admin rights needed).
# MAGIC
# MAGIC A new Git folder may contain only LFS **pointers** (small text files). `git lfs pull` replaces
# MAGIC them with the real content. It's safe to re-run: files already downloaded are skipped.

# COMMAND ----------

import hashlib
import platform
import tarfile
import urllib.request

GIT_LFS_VERSION = "3.8.0"
GIT_LFS_SHA256 = {
    "amd64": "e455e00f15d9b95661b8d53498ffb0c3367962cf1ec73c31ab7369516cd6ab8d",
    "arm64": "ac9c8efac980bb0505ead384d087e2acb6486fd8498691a2165fa174ec6118c2",
}

if subprocess.run(["git", "lfs", "version"], capture_output=True).returncode != 0:
    arch = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
    name = f"git-lfs-linux-{arch}-v{GIT_LFS_VERSION}.tar.gz"
    url = f"https://github.com/git-lfs/git-lfs/releases/download/v{GIT_LFS_VERSION}/{name}"
    install_dir = f"/tmp/git-lfs-{GIT_LFS_VERSION}"
    tarball = f"/tmp/{name}"

    print("git-lfs not found; downloading", url)
    urllib.request.urlretrieve(url, tarball)
    digest = hashlib.sha256(open(tarball, "rb").read()).hexdigest()
    if digest != GIT_LFS_SHA256[arch]:
        raise RuntimeError(f"Checksum mismatch for {name}: {digest}")
    with tarfile.open(tarball) as tf:
        tf.extract(f"git-lfs-{GIT_LFS_VERSION}/git-lfs", "/tmp", filter="data")
    os.makedirs(install_dir, exist_ok=True)
    os.replace(f"/tmp/git-lfs-{GIT_LFS_VERSION}/git-lfs", f"{install_dir}/git-lfs")
    os.chmod(f"{install_dir}/git-lfs", 0o755)
    # Only affects git commands started from this notebook's Python process.
    os.environ["PATH"] = f"{install_dir}:{os.environ['PATH']}"

sh("git lfs version")
sh("git lfs install --local")  # enable LFS for this repo only
_ = sh("git lfs ls-files --size")  # '-' = pointer only, '*' = content downloaded

# COMMAND ----------

_ = sh(f'git lfs pull --include="{LFS_FILE}"')  # drop --include to download every LFS file
_ = sh("git lfs ls-files --size")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Confirm it's real content, not a pointer
# MAGIC
# MAGIC Git itself stores only a ~130-byte pointer with the file's SHA-256 (`oid`) and size. After
# MAGIC `git lfs pull`, the file in the Git folder must match that size and checksum.

# COMMAND ----------

pointer = sh(f"git cat-file -p HEAD:{LFS_FILE}")
fields = dict(line.split(" ", 1) for line in pointer.strip().splitlines())
EXPECTED_OID = fields["oid"].removeprefix("sha256:")
EXPECTED_SIZE = int(fields["size"])


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: str) -> None:
    size = os.path.getsize(path)
    if size != EXPECTED_SIZE or sha256_of(path) != EXPECTED_OID:
        raise RuntimeError(
            f"{path} is {size:,} bytes but the LFS pointer says {EXPECTED_SIZE:,}. "
            "It is probably still a pointer: check the `git lfs pull` output above."
        )
    print(f"OK  {path}  ({size / 1e6:,.1f} MB, sha256 {EXPECTED_OID[:12]}…)")


verify(SRC)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Copy to a workspace folder and a Unity Catalog volume

# COMMAND ----------

import shutil

user = spark.sql("SELECT current_user()").first()[0]
workspace_dir = dbutils.widgets.get("workspace_dir") or f"/Workspace/Users/{user}/lfs_demo_output"
volume_dir = dbutils.widgets.get("volume_dir")

copies = []
for target_dir in (workspace_dir, volume_dir):
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, os.path.basename(LFS_FILE))
    shutil.copyfile(SRC, dest)
    verify(dest)
    copies.append(dest)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Use the copy from the volume

# COMMAND ----------

volume_copy = copies[1]
df = spark.read.parquet(volume_copy)
print(f"{df.count():,} rows read from {volume_copy}")
display(df.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Clean up (optional)
# MAGIC
# MAGIC Removes only the copies this notebook made, not the target folders or the volume.

# COMMAND ----------

# for path in copies:
#     os.remove(path)
