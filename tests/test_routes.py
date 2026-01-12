import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unified_app import app

class TestPortalRoutes(unittest.TestCase):
    def setUp(self):
        # Set base_url to localhost to pass TrustedHostMiddleware
        # follow_redirects=False prevents hitting external OAuth providers during tests
        self.client = TestClient(app, base_url="http://localhost", follow_redirects=False)

    def test_root_endpoint(self):
        """Test that the root endpoint (Portal Dashboard) is reachable."""
        # Should redirect to login if not authenticated
        response = self.client.get("/")
        self.assertIn(response.status_code, [200, 302, 307])

    def test_payroll_endpoint(self):
        """Test that the payroll converter tool is reachable."""
        response = self.client.get("/payroll")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Payroll", response.text)

    def test_sales_dashboard_mount(self):
        """Test that the Sales Dashboard is mounted correctly."""
        # Should redirect to login
        response = self.client.get("/sales/login")
        self.assertIn(response.status_code, [200, 302, 307])

    def test_recruiting_dashboard_mount(self):
        """Test that the Recruiting Dashboard is mounted correctly."""
        # Recruiting is a Flask app mounted via WSGIMiddleware
        response = self.client.get("/recruiting/")
        # Flask usually redirects trailing slash or returns 200/302
        self.assertIn(response.status_code, [200, 302, 307, 308])

if __name__ == '__main__':
    unittest.main()
