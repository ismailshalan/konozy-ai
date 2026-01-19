# Konozy AI Verification Scripts

This directory contains scripts for verifying architecture compliance and running tests.

## Scripts Overview

### 1. `run_architecture_check.sh` (Quick Check - 5-10 seconds)
**Purpose:** Fast domain purity validation  
**Checks:**
- Domain layer purity (no SQLAlchemy, Pydantic, FastAPI imports)
- AST-based import analysis
- Grep-based validation

**Usage:**
```bash
./scripts/run_architecture_check.sh
```

**When to use:**
- Before every commit
- In CI/CD pipelines
- Quick validation during development

---

### 2. `verify_architecture.py` (Full Verification - 30 seconds)
**Purpose:** Comprehensive architecture audit  
**Checks:**
1. Domain Layer Purity
2. Dependency Direction
3. Layer Isolation
4. Import Rules
5. File Structure
6. Database Models
7. API Layer
8. Use Cases
9. Repositories
10. Integration Points

**Usage:**
```bash
python scripts/verify_architecture.py
```

**When to use:**
- Before major releases
- Weekly/monthly architecture reviews
- Before adding complex features (e.g., Event Sourcing)
- Onboarding new developers

---

### 3. `integration_test.py` (Integration Test - 10 seconds)
**Purpose:** End-to-end workflow testing  
**Tests:**
- Complete order sync workflow
- Use case execution
- Repository operations
- Notification service

**Usage:**
```bash
python scripts/integration_test.py
```

**When to use:**
- After major changes
- Before deployment
- Validating complete workflows

---

### 4. `test_coverage.py` (Test Coverage - Variable)
**Purpose:** Generate test coverage reports  
**Features:**
- Runs pytest with coverage
- Generates HTML report
- Shows missing coverage

**Usage:**
```bash
python scripts/test_coverage.py
```

**Requirements:**
```bash
pip install pytest pytest-cov pytest-asyncio
```

**When to use:**
- Before releases
- Regular quality checks
- Identifying untested code

---

### 5. `verify_all.sh` (Complete Suite - 1-2 minutes)
**Purpose:** Run all verification checks  
**Runs:**
1. Quick Architecture Check
2. Full Architecture Verification
3. Integration Test
4. Unit Tests (if pytest installed)

**Usage:**
```bash
./scripts/verify_all.sh
```

**When to use:**
- Before production deployment
- Complete system validation
- Pre-release verification

---

## Recommended Workflow

### Daily Development
```bash
# Quick check before committing
./scripts/run_architecture_check.sh
```

### Weekly Reviews
```bash
# Full verification
python scripts/verify_architecture.py
python scripts/integration_test.py
```

### Pre-Release
```bash
# Complete verification suite
./scripts/verify_all.sh
```

---

## Exit Codes

All scripts follow standard exit codes:
- `0` = Success (all checks passed)
- `1` = Failure (violations or errors found)

This makes them suitable for CI/CD pipelines.

---

## Architecture Rules Enforced

### Domain Purity (ZERO TOLERANCE)
The `core/domain/` directory must NOT contain:
- ❌ SQLAlchemy imports
- ❌ Pydantic imports
- ❌ FastAPI imports
- ❌ Any framework dependencies

**Allowed:**
- ✅ Pure Python dataclasses
- ✅ Standard library (datetime, Decimal, UUID, Enum, abc)
- ✅ Domain entities with business logic
- ✅ Value Objects (immutable types)
- ✅ Repository interfaces (ABC protocols)

### Dependency Direction
Dependencies must flow **INWARDS**:
```
Presentation → Application → Domain ← Infrastructure
```

---

## Troubleshooting

### Script not executable
```bash
chmod +x scripts/*.sh
```

### Python not found
```bash
# Use python3 explicitly
python3 scripts/verify_architecture.py
```

### Import errors
```bash
# Make sure you're in the project root
cd /mnt/storage/Konozy_ai
python scripts/verify_architecture.py
```

### Pytest not found
```bash
pip install pytest pytest-cov pytest-asyncio
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Architecture Check
  run: |
    chmod +x ./scripts/run_architecture_check.sh
    ./scripts/run_architecture_check.sh

- name: Full Architecture Verification
  run: python scripts/verify_architecture.py

- name: Integration Test
  run: python scripts/integration_test.py
```

---

## Notes

- All scripts are designed to be **non-destructive** (read-only checks)
- Scripts will continue running even if some checks fail (except `run_architecture_check.sh` which exits on first violation)
- The `verify_all.sh` script provides a comprehensive summary at the end

