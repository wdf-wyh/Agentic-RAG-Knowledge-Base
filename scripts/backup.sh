#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${1:-./backups}"
BACKUP_DIR="${BACKUP_ROOT}/backup_${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

echo "[backup] target: ${BACKUP_DIR}"

cp -r ./vector_db "${BACKUP_DIR}/vector_db"
cp -r ./conversations "${BACKUP_DIR}/conversations"
cp -r ./logs "${BACKUP_DIR}/logs"
cp -r ./data "${BACKUP_DIR}/data"

if [ -d "./documents" ]; then
  cp -r ./documents "${BACKUP_DIR}/documents"
fi

echo "[backup] done"
