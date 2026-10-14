#!/bin/bash
# ==========================================================
# DivinoGIS - Inicializador Localhost
# ==========================================================
cd "$(dirname "$0")"

PORT=${PORT:-5001}

echo "=========================================================="
echo "  🌐 Iniciando DivinoGIS Web"
echo "  📍 Servidor local: http://localhost:${PORT}"
echo "=========================================================="

python3 app.py
