#!/bin/bash
# Complete Verification Suite
# Konozy AI - Comprehensive Architecture & Integration Verification

set -e

echo "════════════════════════════════════════════════════════════"
echo "🚀 KONOZY AI - COMPLETE VERIFICATION SUITE"
echo "════════════════════════════════════════════════════════════"

# Track results
QUICK_CHECK_PASSED=0
FULL_VERIFICATION_PASSED=0
INTEGRATION_TEST_PASSED=0
UNIT_TESTS_PASSED=0

# 1. Quick Architecture Check (5s)
echo ""
echo "📋 Step 1/4: Quick Architecture Check..."
if ./scripts/run_architecture_check.sh; then
    QUICK_CHECK_PASSED=1
    echo "   ✅ Quick check PASSED"
else
    echo "   ❌ Quick check FAILED"
    echo "   ⚠️  Continuing with other checks..."
fi

# 2. Full Architecture Verification (30s)
echo ""
echo "📋 Step 2/4: Full Architecture Verification..."
if python3 scripts/verify_architecture.py; then
    FULL_VERIFICATION_PASSED=1
    echo "   ✅ Full verification PASSED"
else
    echo "   ❌ Full verification FAILED"
    echo "   ⚠️  Continuing with other checks..."
fi

# 3. Integration Test (10s)
echo ""
echo "📋 Step 3/4: Integration Test..."
if python3 scripts/integration_test.py; then
    INTEGRATION_TEST_PASSED=1
    echo "   ✅ Integration test PASSED"
else
    echo "   ❌ Integration test FAILED"
    echo "   ⚠️  Continuing with other checks..."
fi

# 4. Unit Tests (optional)
echo ""
echo "📋 Step 4/4: Unit Tests..."
if command -v pytest &> /dev/null; then
    if pytest tests/ -v --tb=short 2>/dev/null; then
        UNIT_TESTS_PASSED=1
        echo "   ✅ Unit tests PASSED"
    else
        echo "   ❌ Some unit tests FAILED"
    fi
else
    echo "   ⚠️  Pytest not installed - skipping unit tests"
    echo "   💡 Install with: pip install pytest pytest-asyncio"
    UNIT_TESTS_PASSED=-1  # -1 means skipped
fi

# Summary
echo ""
echo "════════════════════════════════════════════════════════════"
echo "VERIFICATION SUMMARY"
echo "════════════════════════════════════════════════════════════"
echo ""

TOTAL_CHECKS=0
PASSED_CHECKS=0

if [ $QUICK_CHECK_PASSED -eq 1 ]; then
    echo "  ✅ Quick Architecture Check: PASSED"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo "  ❌ Quick Architecture Check: FAILED"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

if [ $FULL_VERIFICATION_PASSED -eq 1 ]; then
    echo "  ✅ Full Architecture Verification: PASSED"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo "  ❌ Full Architecture Verification: FAILED"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

if [ $INTEGRATION_TEST_PASSED -eq 1 ]; then
    echo "  ✅ Integration Test: PASSED"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo "  ❌ Integration Test: FAILED"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

if [ $UNIT_TESTS_PASSED -eq 1 ]; then
    echo "  ✅ Unit Tests: PASSED"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
elif [ $UNIT_TESTS_PASSED -eq -1 ]; then
    echo "  ⚠️  Unit Tests: SKIPPED (pytest not installed)"
else
    echo "  ❌ Unit Tests: FAILED"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Results: $PASSED_CHECKS/$TOTAL_CHECKS checks passed"
echo "════════════════════════════════════════════════════════════"

# Determine overall status
if [ $QUICK_CHECK_PASSED -eq 1 ] && [ $FULL_VERIFICATION_PASSED -eq 1 ] && [ $INTEGRATION_TEST_PASSED -eq 1 ]; then
    echo ""
    echo "✅ COMPLETE VERIFICATION PASSED"
    echo ""
    echo "Results:"
    echo "  ✅ Architecture: Clean"
    echo "  ✅ Dependencies: Correct"
    echo "  ✅ Integration: Working"
    if [ $UNIT_TESTS_PASSED -eq 1 ]; then
        echo "  ✅ Tests: Passing"
    else
        echo "  ⚠️  Tests: Not run or failed"
    fi
    echo ""
    echo "🎉 System is healthy and ready!"
    echo "════════════════════════════════════════════════════════════"
    exit 0
else
    echo ""
    echo "❌ VERIFICATION FAILED"
    echo ""
    echo "Some checks did not pass. Please review the errors above."
    echo "════════════════════════════════════════════════════════════"
    exit 1
fi

