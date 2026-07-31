#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ./scripts/restore.sh <backup_dir>"
  exit 1
fi

BACKUP_DIR="$1"
if [ ! -d "${BACKUP_DIR}" ]; then
  echo "[restore] backup directory not found: ${BACKUP_DIR}"
  exit 1
fi

echo "[restore] source: ${BACKUP_DIR}"

if [ -d "${BACKUP_DIR}/vector_db" ]; then
  rm -rf ./vector_db
  cp -r "${BACKUP_DIR}/vector_db" ./vector_db
fi

if [ -d "${BACKUP_DIR}/conversations" ]; then
  rm -rf ./conversations
  cp -r "${BACKUP_DIR}/conversations" ./conversations
fi

if [ -d "${BACKUP_DIR}/logs" ]; then
  rm -rf ./logs
  cp -r "${BACKUP_DIR}/logs" ./logs
fi

if [ -d "${BACKUP_DIR}/data" ]; then
  rm -rf ./data
  cp -r "${BACKUP_DIR}/data" ./data
fi

if [ -d "${BACKUP_DIR}/documents" ]; then
  rm -rf ./documents
  cp -r "${BACKUP_DIR}/documents" ./documents
fi

echo "[restore] done"
