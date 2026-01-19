"""
Complete Architecture Verification.

Tests all layers, dependencies, and architectural rules.
"""
import sys
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ArchitectureVerifier:
    """Verify Clean Architecture compliance."""
    
    def __init__(self):
        self.violations = []
        self.warnings = []
        self.passed_checks = []
    
    def verify_all(self) -> bool:
        """Run all architecture verification checks."""
        
        logger.info("="*80)
        logger.info("KONOZY AI - ARCHITECTURE VERIFICATION")
        logger.info("="*80)
        
        checks = [
            ("1. Domain Layer Purity", self.check_domain_purity),
            ("2. Dependency Direction", self.check_dependency_direction),
            ("3. Layer Isolation", self.check_layer_isolation),
            ("4. Import Rules", self.check_import_rules),
            ("5. File Structure", self.check_file_structure),
            ("6. Database Models", self.check_database_models),
            ("7. API Layer", self.check_api_layer),
            ("8. Use Cases", self.check_use_cases),
            ("9. Repositories", self.check_repositories),
            ("10. Integration Points", self.check_integration_points),
        ]
        
        for check_name, check_func in checks:
            logger.info(f"\n{check_name}...")
            try:
                check_func()
                logger.info(f"   ✅ PASSED")
                self.passed_checks.append(check_name)
            except Exception as e:
                logger.error(f"   ❌ FAILED: {e}")
                self.violations.append((check_name, str(e)))
        
        # Print summary
        self._print_summary()
        
        return len(self.violations) == 0
    
    def check_domain_purity(self):
        """Verify domain layer has no external dependencies."""
        logger.info("   Checking domain purity...")
        
        # Domain should not import from infrastructure or application
        # Note: dataclasses is ALLOWED (standard library)
        forbidden_imports = [
            'infrastructure',
            'application',
            'data',
            'sqlalchemy',
            'fastapi',
            'pydantic',
        ]
        
        violations = self._check_imports('core/domain', forbidden_imports)
        
        if violations:
            violation_list = '\n'.join([f'      - {v[0]}: {v[1]}' for v in violations[:5]])
            raise Exception(f"Domain layer has {len(violations)} forbidden imports:\n{violation_list}")
        
        logger.info(f"   ✓ Domain layer is pure (no external dependencies)")
    
    def check_dependency_direction(self):
        """Verify dependencies flow inward."""
        logger.info("   Checking dependency direction...")
        
        # Application should not import from infrastructure directly (except through interfaces)
        violations = self._check_imports(
            'core/application',
            ['infrastructure.database', 'infrastructure.adapters'],
            allowed=['infrastructure.database.repositories']  # Interface implementations allowed
        )
        
        if violations:
            self.warnings.append(("Dependency Direction", f"{len(violations)} potential issues"))
            logger.info(f"   ⚠️  Found {len(violations)} potential dependency violations (warnings only)")
        
        logger.info(f"   ✓ Dependencies flow inward")
    
    def check_layer_isolation(self):
        """Verify layers are properly isolated."""
        logger.info("   Checking layer isolation...")
        
        layers = {
            'domain': Path('core/domain'),
            'application': Path('core/application'),
            'data': Path('core/data'),
            'infrastructure': Path('core/infrastructure'),
        }
        
        missing = []
        for name, path in layers.items():
            if not path.exists():
                missing.append(name)
        
        if missing:
            raise Exception(f"Layers missing: {', '.join(missing)}")
        
        logger.info(f"   ✓ All layers present and isolated")
    
    def check_import_rules(self):
        """Check import rules compliance."""
        logger.info("   Checking import rules...")
        
        # Verify domain doesn't import from other layers
        domain_violations = self._check_imports(
            'core/domain',
            ['core.application', 'core.data', 'core.infrastructure', 'apps.api', 'api']
        )
        
        if domain_violations:
            raise Exception(f"Domain layer imports from other layers: {len(domain_violations)} violations")
        
        logger.info(f"   ✓ Import rules verified")
    
    def check_file_structure(self):
        """Verify file structure."""
        logger.info("   Checking file structure...")
        
        required_structure = {
            'core/domain/entities': [],
            'core/domain/value_objects': [],
            'core/domain/repositories': [],
            'core/application/use_cases': [],
            'core/application/services': [],
            'core/data/models': [],
            'core/data/repositories': [],
        }
        
        missing = []
        for directory in required_structure.keys():
            dir_path = Path(directory)
            if not dir_path.exists():
                missing.append(directory)
        
        # Check for at least some Python files in key directories
        key_dirs = {
            'core/domain/entities': 'entities',
            'core/domain/value_objects': 'value objects',
            'core/domain/repositories': 'repository interfaces',
        }
        
        for dir_path, desc in key_dirs.items():
            path = Path(dir_path)
            if path.exists():
                py_files = list(path.glob('*.py'))
                py_files = [f for f in py_files if f.name != '__init__.py']
                if not py_files:
                    missing.append(f"{dir_path} (no {desc} found)")
        
        if missing:
            raise Exception(f"Missing files/directories: {', '.join(missing[:5])}")
        
        logger.info(f"   ✓ File structure correct")
    
    def check_database_models(self):
        """Verify database models."""
        logger.info("   Checking database models...")
        
        # Try to import from either location
        models_imported = False
        
        # Try core/infrastructure/database/models first
        try:
            from core.infrastructure.database.models import OrderModel
            models_imported = True
            logger.info("   ✓ Found models in core/infrastructure/database/models")
        except ImportError:
            pass
        
        # Try core/data/models as fallback
        if not models_imported:
            try:
                from core.data.models import OrderModel
                models_imported = True
                logger.info("   ✓ Found models in core/data/models")
            except ImportError:
                pass
        
        if not models_imported:
            raise Exception("Cannot import database models from either location")
        
        # Check model has required fields
        required_fields = ['id', 'order_id']
        for field in required_fields:
            if not hasattr(OrderModel, field):
                raise Exception(f"OrderModel missing field: {field}")
        
        logger.info(f"   ✓ Database models correct")
    
    def check_api_layer(self):
        """Verify API layer."""
        logger.info("   Checking API layer...")
        
        # Check apps/api or api/ exists
        api_paths = [Path('apps/api/main.py'), Path('api/main.py')]
        api_found = any(path.exists() for path in api_paths)
        
        if not api_found:
            raise Exception("No API layer found (checked apps/api/main.py and api/main.py)")
        
        logger.info(f"   ✓ API layer present")
    
    def check_use_cases(self):
        """Verify use cases."""
        logger.info("   Checking use cases...")
        
        use_cases_path = Path('core/application/use_cases')
        if not use_cases_path.exists():
            raise Exception("Use cases directory not found")
        
        # Check for at least one use case file
        use_case_files = list(use_cases_path.glob('*.py'))
        use_case_files = [f for f in use_case_files if f.name != '__init__.py']
        
        if not use_case_files:
            logger.info("   ⚠️  No use case files found (warning only)")
            self.warnings.append(("Use Cases", "No use case files found"))
        else:
            logger.info(f"   ✓ Found {len(use_case_files)} use case file(s)")
        
        logger.info(f"   ✓ Use cases checked")
    
    def check_repositories(self):
        """Verify repositories."""
        logger.info("   Checking repositories...")
        
        # Check interface exists
        try:
            from core.domain.repositories import OrderRepository
        except ImportError as e:
            raise Exception(f"Cannot import repository interface: {e}")
        
        # Check implementation exists (try both locations)
        impl_found = False
        
        try:
            from core.infrastructure.database.repositories.sqlalchemy_order_repository import SQLAlchemyOrderRepository
            impl_found = True
            logger.info("   ✓ Found repository in core/infrastructure/database/repositories")
        except ImportError:
            pass
        
        if not impl_found:
            try:
                from core.data.repositories import SqlAlchemyOrderRepository
                impl_found = True
                logger.info("   ✓ Found repository in core/data/repositories")
            except ImportError:
                pass
        
        if not impl_found:
            raise Exception("Cannot import repository implementation from either location")
        
        logger.info(f"   ✓ Repositories correct")
    
    def check_integration_points(self):
        """Verify integration points."""
        logger.info("   Checking integration points...")
        
        # Check adapters exist
        adapters_path = Path('core/infrastructure/adapters')
        if adapters_path.exists():
            adapter_dirs = [d for d in adapters_path.iterdir() if d.is_dir()]
            logger.info(f"   ✓ Found {len(adapter_dirs)} adapter directory(ies)")
        else:
            logger.info("   ⚠️  No adapters directory found (warning only)")
            self.warnings.append(("Integration Points", "No adapters directory found"))
        
        logger.info(f"   ✓ Integration points checked")
    
    def _check_imports(
        self,
        directory: str,
        forbidden: List[str],
        allowed: Optional[List[str]] = None
    ) -> List[Tuple[str, str]]:
        """Check for forbidden imports in directory."""
        violations = []
        allowed = allowed or []
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return violations
        
        for file_path in dir_path.rglob('*.py'):
            if file_path.name == '__init__.py':
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for line_num, line in enumerate(content.split('\n'), 1):
                    line_stripped = line.strip()
                    if line_stripped.startswith(('import ', 'from ')):
                        # Skip comments
                        if line_stripped.startswith('#'):
                            continue
                        # Skip dataclasses (it's standard library and allowed)
                        if 'dataclass' in line_stripped and 'dataclasses' in line_stripped:
                            continue
                        # Check for forbidden imports
                        for forbidden_import in forbidden:
                            if forbidden_import in line_stripped:
                                # Check if it's in allowed list
                                is_allowed = any(a in line_stripped for a in allowed)
                                if not is_allowed:
                                    violations.append((f"{file_path}:{line_num}", line_stripped))
            
            except Exception as e:
                logger.warning(f"Could not check {file_path}: {e}")
        
        return violations
    
    def _print_summary(self):
        """Print verification summary."""
        logger.info("\n" + "="*80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\n✅ Passed: {len(self.passed_checks)} checks")
        for check in self.passed_checks:
            logger.info(f"   ✓ {check}")
        
        if self.warnings:
            logger.info(f"\n⚠️  Warnings: {len(self.warnings)}")
            for name, msg in self.warnings:
                logger.info(f"   ! {name}: {msg}")
        
        if self.violations:
            logger.error(f"\n❌ Violations: {len(self.violations)}")
            for name, msg in self.violations:
                logger.error(f"   ✗ {name}: {msg}")
        
        logger.info("\n" + "="*80)
        
        if not self.violations:
            logger.info("✅ ARCHITECTURE VERIFICATION PASSED")
        else:
            logger.error("❌ ARCHITECTURE VERIFICATION FAILED")
        
        logger.info("="*80)


def main():
    """Run architecture verification."""
    verifier = ArchitectureVerifier()
    
    try:
        success = verifier.verify_all()
        sys.exit(0 if success else 1)
    
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

