# Databricks notebook source
# MAGIC %md
# MAGIC # Copy a Git LFS file to a Unity Catalog volume
# MAGIC
# MAGIC This notebook downloads a large file stored with Git LFS into this Git folder, copies it to a
# MAGIC Unity Catalog volume, and reads it from the volume.
# MAGIC
# MAGIC Run it on serverless compute (environment version 5 or above) or a cluster with Databricks Runtime 17.0 or above.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install Git LFS
# MAGIC
# MAGIC Serverless compute includes Git LFS. On classic compute, this cell downloads the official Git LFS
# MAGIC release, checks its SHA-256 checksum, and makes it available to the rest of this notebook.
# MAGIC Nothing is installed on the cluster itself.
# MAGIC
# MAGIC This cell uses Git LFS version 3.8.0. To use a different version, update `version` and both
# MAGIC checksums with the values from that release's `sha256sums.asc` file on the
# MAGIC [Git LFS releases page](https://github.com/git-lfs/git-lfs/releases).

# COMMAND ----------

import hashlib
import os
import platform
import shutil
import tarfile
import urllib.request

if shutil.which("git-lfs") is None:
    version = "3.8.0"
    checksums = {
        "amd64": "e455e00f15d9b95661b8d53498ffb0c3367962cf1ec73c31ab7369516cd6ab8d",
        "arm64": "ac9c8efac980bb0505ead384d087e2acb6486fd8498691a2165fa174ec6118c2",
    }
    arch = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
    tarball = f"/tmp/git-lfs-linux-{arch}-v{version}.tar.gz"
    urllib.request.urlretrieve(
        f"https://github.com/git-lfs/git-lfs/releases/download/v{version}/git-lfs-linux-{arch}-v{version}.tar.gz",
        tarball,
    )
    if hashlib.sha256(open(tarball, "rb").read()).hexdigest() != checksums[arch]:
        raise RuntimeError("Git LFS download failed checksum verification")

    install_dir = "/tmp/git-lfs-bin"
    os.makedirs(install_dir, exist_ok=True)
    with tarfile.open(tarball) as tf:
        member = tf.getmember(f"git-lfs-{version}/git-lfs")
        member.name = "git-lfs"
        tf.extract(member, install_dir, filter="data")
    os.chmod(f"{install_dir}/git-lfs", 0o755)
    os.environ["PATH"] = f"{install_dir}:{os.environ['PATH']}"

print(shutil.which("git-lfs"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up Git LFS
# MAGIC
# MAGIC Check the Git LFS version, turn on Git LFS for this repository, and list the files it tracks.
# MAGIC In the list, `-` means only a small pointer file is present and `*` means the full file is downloaded.

# COMMAND ----------

# MAGIC %sh
# MAGIC cd "$(git rev-parse --show-toplevel)"
# MAGIC git lfs version
# MAGIC git lfs install --local
# MAGIC git lfs ls-files --size

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download the files
# MAGIC
# MAGIC Download the full content of the Git LFS files. Each file should now show `*`.

# COMMAND ----------

# MAGIC %sh
# MAGIC cd "$(git rev-parse --show-toplevel)"
# MAGIC git lfs pull
# MAGIC git lfs ls-files --size

# COMMAND ----------

# MAGIC %md
# MAGIC ## Copy the file to a volume
# MAGIC
# MAGIC Copy the Parquet file to a folder in a Unity Catalog volume. Change the path to a volume you can write to.

# COMMAND ----------

# MAGIC %sh
# MAGIC cd "$(git rev-parse --show-toplevel)"
# MAGIC mkdir -p /Volumes/devanshu_pandey/boc/documents/lfs_demo
# MAGIC cp data/transactions.parquet /Volumes/devanshu_pandey/boc/documents/lfs_demo/
# MAGIC ls -lh /Volumes/devanshu_pandey/boc/documents/lfs_demo/

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read the file from the volume

# COMMAND ----------

df = spark.read.parquet("/Volumes/devanshu_pandey/boc/documents/lfs_demo/transactions.parquet")
print(f"{df.count():,} rows")
display(df.limit(10))
