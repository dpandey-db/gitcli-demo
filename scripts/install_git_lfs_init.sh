#!/bin/bash
# Cluster init script: installs Git LFS on classic Databricks compute (DBR 17.0+).
# Serverless compute already includes git-lfs; classic DBR does not.
#
# Attach under Compute -> <cluster> -> Advanced -> Init scripts, from a workspace file or
# a Unity Catalog volume. After this, `git clone` (web terminal or notebook) downloads
# LFS content automatically.
set -euo pipefail

GIT_LFS_VERSION="3.8.0"
case "$(uname -m)" in
  x86_64)  ARCH=amd64; SHA256=e455e00f15d9b95661b8d53498ffb0c3367962cf1ec73c31ab7369516cd6ab8d ;;
  aarch64) ARCH=arm64; SHA256=ac9c8efac980bb0505ead384d087e2acb6486fd8498691a2165fa174ec6118c2 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

if command -v git-lfs >/dev/null 2>&1; then
  echo "git-lfs already installed: $(git-lfs version)"
  exit 0
fi

NAME="git-lfs-linux-${ARCH}-v${GIT_LFS_VERSION}.tar.gz"
TMP="$(mktemp -d)"
curl -fsSL -o "${TMP}/${NAME}" \
  "https://github.com/git-lfs/git-lfs/releases/download/v${GIT_LFS_VERSION}/${NAME}"
echo "${SHA256}  ${TMP}/${NAME}" | sha256sum -c -
tar -xzf "${TMP}/${NAME}" -C "${TMP}"
install -m 0755 "${TMP}/git-lfs-${GIT_LFS_VERSION}/git-lfs" /usr/local/bin/git-lfs
git lfs install --system
rm -rf "${TMP}"
echo "Installed $(git-lfs version)"
