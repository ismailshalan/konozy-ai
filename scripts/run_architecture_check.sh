#!/bin/bash
# scripts/run_architecture_check.sh
# Konozy AI Architecture Validation Script

set -e

echo "🔍 Running Konozy AI Architecture Validation..."

# 1. Domain Purity Check
echo "Checking domain purity..."
python3 -c "
import ast
import sys
from pathlib import Path

prohibited = ['sqlalchemy', 'pydantic', 'fastapi']
violations = []

for file in Path('core/domain').rglob('*.py'):
    if file.name == '__init__.py':
        continue
    try:
        with open(file) as f:
            tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and any(p in node.module for p in prohibited):
                        violations.append(f'{file}: imports {node.module}')
    except Exception as e:
        print(f'Error parsing {file}: {e}')
        sys.exit(1)

if violations:
    print('❌ Domain purity violations:')
    for v in violations:
        print(f'  - {v}')
    sys.exit(1)
else:
    print('✅ Domain purity validated')
"

# 2. Grep-based checks for additional safety
echo "Running grep-based validation..."
if grep -r "from sqlalchemy" core/domain/ 2>/dev/null; then
    echo "❌ VIOLATION DETECTED: SQLAlchemy import found in core/domain/"
    exit 1
fi

if grep -r "from pydantic" core/domain/ 2>/dev/null; then
    echo "❌ VIOLATION DETECTED: Pydantic import found in core/domain/"
    exit 1
fi

if grep -r "from fastapi" core/domain/ 2>/dev/null; then
    echo "❌ VIOLATION DETECTED: FastAPI import found in core/domain/"
    exit 1
fi

echo "✅ Grep-based validation passed"

# 3. Architecture Violations Summary
echo ""
echo "═══════════════════════════════════════"
echo "Architecture Violations: 0"
echo "═══════════════════════════════════════"
echo "✅ ALL QUALITY GATES PASSED"
echo "✅ READY FOR DEPLOYMENT"
