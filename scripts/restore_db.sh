#!/usr/bin/env bash
# ==============================================================================
# SCRIPT RESTORE DATABASE POSTGRESQL CHO AI AUTO VIDEO PUBLISHER 24/7
# ==============================================================================

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Cách dùng: $0 <duong_dan_file_backup.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
CONTAINER_NAME="${POSTGRES_CONTAINER:-auto_post_postgres}"
POSTGRES_USER="${POSTGRES_USER:-app_user}"
POSTGRES_DB="${POSTGRES_DB:-auto_post_db}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Lỗi: Không tìm thấy tệp backup: ${BACKUP_FILE}"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] CẢNH BÁO: Thao tác này sẽ ghi đè toàn bộ database ${POSTGRES_DB}!"
read -p "Bạn có chắc chắn muốn khôi phục? (y/N): " -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Đã hủy thao tác khôi phục."
    exit 0
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Đang giải nén và khôi phục vào container ${CONTAINER_NAME}..."
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Khôi phục dữ liệu thành công!"
