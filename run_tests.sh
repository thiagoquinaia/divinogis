#!/usr/bin/env bash
set -e

echo "======================================================="
echo "  DivinoGIS - Executando Suíte de Testes e Validação   "
echo "======================================================="

# 1. Validação de sintaxe Python
echo "🔍 1. Validando sintaxe Python..."
python3 -m py_compile app.py srtm_service.py stl_service.py ibge_service.py net_utils.py
echo "✓ Sintaxe Python 100% válida."

# 2. Validação de sintaxe JavaScript
if command -v node >/dev/null 2>&1; then
    echo "🔍 2. Validando sintaxe JavaScript (Node.js)..."
    node -c static/js/app.js
    echo "✓ Sintaxe JavaScript 100% válida."
else
    echo "⚠️ Node.js não encontrado; pulando validação estática de JS."
fi

# 3. Execução dos testes automatizados com pytest
echo "🧪 3. Executando testes unitários e de integração (pytest)..."
python3 -m pytest tests/ -v --tb=short

echo ""
echo "======================================================="
echo "  ✅ TODOS OS TESTES PASSARAM COM SUCESSO!             "
echo "  O código está seguro e pronto para commit/push.      "
echo "======================================================="
