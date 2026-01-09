import os
import sys
import unittest
from sqlalchemy import text

# Set test database URL before importing modules that use it
# Use in-memory SQLite for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_manager
from models import Base, Contact, Deal, Lead
import add_december_2025_leads

class TestImportIdempotency(unittest.TestCase):
    def setUp(self):
        # Create tables
        Base.metadata.create_all(bind=db_manager.engine)
        self.session = db_manager.get_session()
        
        # Initialize pipeline stages (required for import)
        from models import PipelineStage
        stages = [
            PipelineStage(name="Incoming Leads", order_index=1, weighting=0.10),
            PipelineStage(name="Ongoing Leads", order_index=2, weighting=0.40),
            PipelineStage(name="Pending", order_index=3, weighting=0.80),
            PipelineStage(name="Closed/Won", order_index=4, weighting=1.00),
        ]
        self.session.add_all(stages)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=db_manager.engine)

    def test_import_idempotency(self):
        # Clear global stage cache to prevent DetachedInstanceError across sessions
        add_december_2025_leads.stage_cache = {}

        # Initial run
        print("\n--- Running Import (Round 1) ---")
        add_december_2025_leads.main()
        
        # Check counts
        lead_count_1 = self.session.query(Lead).count()
        contact_count_1 = self.session.query(Contact).count()
        deal_count_1 = self.session.query(Deal).count()
        
        print(f"Round 1: Leads={lead_count_1}, Contacts={contact_count_1}, Deals={deal_count_1}")
        
        # Verify we have data
        self.assertGreater(lead_count_1, 0, "Should have imported leads")
        self.assertGreater(contact_count_1, 0, "Should have created contacts")
        self.assertGreater(deal_count_1, 0, "Should have created deals")

        # Clear global stage cache again for the second run
        add_december_2025_leads.stage_cache = {}

        # Second run
        print("\n--- Running Import (Round 2) ---")
        add_december_2025_leads.main()
        
        # Check counts again
        lead_count_2 = self.session.query(Lead).count()
        contact_count_2 = self.session.query(Contact).count()
        deal_count_2 = self.session.query(Deal).count()
        
        print(f"Round 2: Leads={lead_count_2}, Contacts={contact_count_2}, Deals={deal_count_2}")
        
        # Verify idempotency
        self.assertEqual(lead_count_1, lead_count_2, "Lead count should not change")
        self.assertEqual(contact_count_1, contact_count_2, "Contact count should not change")
        self.assertEqual(deal_count_1, deal_count_2, "Deal count should not change")

if __name__ == "__main__":
    unittest.main()
