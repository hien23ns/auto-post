#!/usr/bin/env bash
# ==============================================================================
# SCRIPT BACKUP DATABASE POSTGRESQL CHO AI AUTO VIDEO PUBLISHER 24/7
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/auto_post_db}"
DATE_STR=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/auto_post_db_${DATE_STR}.sql.gz"
CONTAINER_NAME="${POSTGRES_CONTAINER:-auto_post_postgres}"
POSTGRES_USER="${POSTGRES_USER:-app_user}"
POSTGRES_DB="${POSTGRES_DB:-auto_post_db}"
RETENTION_DAYS=14

mkdir -p "${BACKUP_DIR}"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Bắt đầu backup database ${POSTGRES_DB} từ container ${CONTAINER_NAME}..."

docker exec -t "${CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${BACKUP_FILE}"

FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup hoàn tất thành công! Tệp: ${BACKUP_FILE} (Dung lượng: ${FILE_SIZE})"

# Xóa các bản backup cũ hơn 14 ngày
find "${BACKUP_DIR}" -type f -name "auto_post_db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Đã dọn dẹp các bản backup cũ hơn ${RETENTION_DAYS} ngày."
