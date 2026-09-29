#!/usr/bin/env bash
# ==============================================================================
# Script de Respaldo Integral: PostgreSQL + Odoo Filestore + Addons
# Sistema Integral de Flota de Buses Odoo 18 + GPS Broker
# ==============================================================================
set -eo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/flota}"
TEMP_DIR="${BACKUP_DIR}/temp_${TIMESTAMP}"
RETENTION_DAYS=7 # Días de conservación local

DB_CONTAINER="odoo_transporte_db"
DB_USER="odoo"
DB_NAME="flota_db"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ODOO_FILESTORE_VOLUME="transporte_odoo_odoo-web-data"
FINAL_ARCHIVE="${BACKUP_DIR}/backup_completo_${DB_NAME}_${TIMESTAMP}.tar.gz"

echo "[ $(date) ] Iniciando proceso de respaldo..."
mkdir -p "${TEMP_DIR}/db"
mkdir -p "${TEMP_DIR}/filestore"
mkdir -p "${TEMP_DIR}/config_custom"

# 1. Dump binario comprimido de PostgreSQL
echo "[ $(date) ] Extrayendo dump de PostgreSQL (${DB_NAME})..."
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -b -v -f "/tmp/db_dump_${TIMESTAMP}.dump"
docker cp "${DB_CONTAINER}:/tmp/db_dump_${TIMESTAMP}.dump" "${TEMP_DIR}/db/${DB_NAME}.dump"
docker exec "${DB_CONTAINER}" rm "/tmp/db_dump_${TIMESTAMP}.dump"

# 2. Respaldo del Filestore de Odoo
echo "[ $(date) ] Copiando filestore de Odoo..."
docker run --rm -v "${ODOO_FILESTORE_VOLUME}:/data:ro" -v "${TEMP_DIR}/filestore:/backup" alpine cp -a /data/filestore /backup/ || true

# 3. Respaldo de Addons y Configuración
echo "[ $(date) ] Respaldando addons y configuraciones..."
cp -r "${PROJECT_DIR}/custom_addons" "${TEMP_DIR}/config_custom/"
cp -r "${PROJECT_DIR}/config" "${TEMP_DIR}/config_custom/"
cp "${PROJECT_DIR}/docker-compose.yml" "${TEMP_DIR}/config_custom/"

# 4. Empaquetar y comprimir archivo final .tar.gz
echo "[ $(date) ] Comprimiendo archivo final..."
tar -czf "${FINAL_ARCHIVE}" -C "${TEMP_DIR}" .
rm -rf "${TEMP_DIR}"

echo "[ $(date) ] Respaldo finalizado con éxito: ${FINAL_ARCHIVE} ($(du -h "${FINAL_ARCHIVE}" | awk '{print $1}'))"

# 5. Rotación de backups locales antiguos (> 7 días)
find "${BACKUP_DIR}" -name "backup_completo_*.tar.gz" -mtime +${RETENTION_DAYS} -exec rm -f {} \;

# 6. Sincronización a la nube con Rclone (Opcional - Configurar 'remote_drive' o S3)
# if command -v rclone &> /dev/null; then
#     echo "[ $(date) ] Sincronizando respaldo hacia la nube..."
#     rclone copy "${FINAL_ARCHIVE}" remote_drive:backups_flota/
# fi
