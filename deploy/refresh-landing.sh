#!/bin/bash
# Refresca la landing en producción tras un commit.
# Uso (desde tu máquina local):
#   ./deploy/refresh-landing.sh
#
# Pre-requisito: haber hecho `git push` con tus cambios.

set -e

BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "→ Refrescando landing en korio.es (rama: $BRANCH)..."

ssh korio-vps "cd /root/korio && git pull origin $BRANCH" | grep -E 'landing/|index.html|^Updating|^Already'

# Las landing son ficheros estáticos servidos por FastAPI vía StaticFiles.
# No requiere reinicio del servicio.

echo "✓ Listo. Visita https://korio.es/ y haz hard refresh (Cmd+Shift+R)."
