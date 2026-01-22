#!/bin/bash
# scripts/run_architecture_check.sh
# Konozy AI Architecture Validation Script

set -e

echo "🔍 Running Konozy AI Architecture Validation..."

# Check if core/domain directory exists
if [ ! -d "core/domain" ]; then
    echo "❌ ERROR: core/domain directory not found"
    exit 1
fi

# 1. Domain Purity Check (AST-based)
echo "Checking domain purity (AST analysis)..."
python3 - <<'PY'
import ast
import sys
from pathlib import Path

prohibited = ['sqlalchemy', 'pydantic', 'fastapi']
violations = []

for file in Path('core/domain').rglob('*.py'):
    if file.name == '__init__.py':
        continue
    try:
        with open(file, encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file))
            for node in ast.walk(tree):
                # Check ImportFrom statements (from X import Y)
                if isinstance(node, ast.ImportFrom):
                    if node.module and any(p in node.module for p in prohibited):
                        violations.append(f'{file}: imports {node.module}')
                # Check Import statements (import X)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(p in alias.name for p in prohibited):
                            violations.append(f'{file}: imports {alias.name}')
    except SyntaxError as e:
        print(f'❌ Syntax error in {file}: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'❌ Error parsing {file}: {e}')
        sys.exit(1)

if violations:
    print('❌ Domain purity violations:')
    for v in violations:
        print(f'  - {v}')
    sys.exit(1)
else:
    print('✅ Domain purity validated (AST)')
"

# 2. Grep-based checks for additional safety (catches edge cases)
echo "Running grep-based validation..."
violations_found=0

# Check for "from X import" patterns
for framework in sqlalchemy pydantic fastapi; do
    if grep -r "from ${framework}" core/domain/ 2>/dev/null; then
        echo "❌ VIOLATION DETECTED: ${framework^} import found in core/domain/"
        violations_found=1
    fi
done

# Check for "import X" patterns (including "import X as Y")
for framework in sqlalchemy pydantic fastapi; do
    if grep -rE "^import ${framework}( |$| as)" core/domain/ 2>/dev/null; then
        echo "❌ VIOLATION DETECTED: ${framework^} import found in core/domain/"
        violations_found=1
    fi
done

if [ $violations_found -eq 1 ]; then
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
