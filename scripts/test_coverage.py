"""
Test Coverage Report.

Shows test coverage across all layers.
"""
import subprocess
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def run_coverage():
    """Run tests with coverage."""
    
    logger.info("="*80)
    logger.info("TEST COVERAGE REPORT")
    logger.info("="*80)
    
    try:
        # Run pytest with coverage
        result = subprocess.run(
            [
                'pytest',
                'tests/',
                '--cov=core',
                '--cov-report=term-missing',
                '--cov-report=html',
                '-v'
            ],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            logger.info("\n✅ All tests passed!")
        else:
            logger.error("\n❌ Some tests failed")
            if result.stderr:
                print(result.stderr)
        
        logger.info("\n" + "="*80)
        logger.info("Coverage report generated in: htmlcov/index.html")
        logger.info("="*80)
        
        return result.returncode == 0
    
    except FileNotFoundError:
        logger.error("❌ pytest not found. Install with: pip install pytest pytest-cov")
        logger.info("\n💡 To install dependencies:")
        logger.info("   pip install pytest pytest-cov pytest-asyncio")
        return False
    except Exception as e:
        logger.error(f"❌ Coverage failed: {e}")
        return False


if __name__ == "__main__":
    success = run_coverage()
    sys.exit(0 if success else 1)

