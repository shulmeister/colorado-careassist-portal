import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestConnectivity(unittest.TestCase):
    def test_imports(self):
        """Test that critical modules can be imported without error."""
        try:
            import portal.portal_app
            import services.marketing.metrics_service
            import services.marketing.gbp_service
            import unified_app
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_directory_structure(self):
        """Test that critical directories exist."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        required_dirs = [
            'portal',
            'sales',
            'recruiting',
            'services',
            'services/marketing'
        ]
        for d in required_dirs:
            path = os.path.join(root, d)
            self.assertTrue(os.path.isdir(path), f"Directory missing: {d}")

if __name__ == '__main__':
    unittest.main()
