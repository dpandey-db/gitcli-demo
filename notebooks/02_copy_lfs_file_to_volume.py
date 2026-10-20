# Databricks notebook source
# MAGIC %md
# MAGIC # Copy a Git LFS file to a Unity Catalog volume
# MAGIC
# MAGIC This notebook downloads a large file stored with Git LFS into this Git folder, copies it to a
# MAGIC Unity Catalog volume, and reads it from the volume.
# MAGIC
# MAGIC Run it on serverless compute (environment version 5 or above) or on a cluster with Git LFS installed.

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
