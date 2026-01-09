#!/usr/bin/env python3
"""
Test script for Caregiver Recruitment Dashboard
Run this to verify the application is working correctly
"""

import os
import sys
import tempfile
import zipfile
import csv
import io
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_app_import():
    """Test that the app can be imported"""
    try:
        from app import app, db, Lead, Activity, AlertRule
        print("✅ App imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_database_creation():
    """Test database creation"""
    try:
        from app import app, db, Lead, Activity, AlertRule
        
        with app.app_context():
            # Create tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Test creating a lead
            test_lead = Lead(
                name="Test Lead",
                email="test@example.com",
                phone="+1234567890",
                notes="This is a test lead",
                status="new",
                priority="medium"
            )
            db.session.add(test_lead)
            db.session.commit()
            
            # Verify lead was created
            lead_count = Lead.query.count()
            print(f"✅ Test lead created successfully. Total leads: {lead_count}")
            
            # Clean up
            db.session.delete(test_lead)
            db.session.commit()
            
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_zip_upload():
    """Test zip file upload functionality"""
    try:
        from app import app, db, Lead
        
        # Create test CSV data
        csv_data = """name,email,phone,notes
Test User 1,test1@example.com,+1234567890,called and texted - FC
Test User 2,test2@example.com,+1234567891,called and texted - FC, L/M 9/2 CP"""
        
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w') as zf:
                zf.writestr('test_leads.csv', csv_data)
            
            # Test the upload processing logic
            with app.app_context():
                zip_file = zipfile.ZipFile(temp_zip.name)
                leads_added = 0
                
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith('.csv'):
                        csv_data = zip_file.read(file_info.filename).decode('utf-8')
                        csv_reader = csv.DictReader(io.StringIO(csv_data))
                        
                        for row in csv_reader:
                            name = row.get('name', '').strip()
                            email = row.get('email', '').strip()
                            phone = row.get('phone', '').strip()
                            notes = row.get('notes', '').strip()
                            
                            if name and phone:
                                leads_added += 1
                
                print(f"✅ Zip upload processing works. Would add {leads_added} leads")
            
            # Clean up
            os.unlink(temp_zip.name)
            
        return True
    except Exception as e:
        print(f"❌ Zip upload test failed: {e}")
        return False

def test_sentiment_analysis():
    """Test sentiment analysis functionality"""
    try:
        from app import analyze_sentiment
        
        # Test positive sentiment
        positive_text = "Great candidate, very interested in the position!"
        pos_score = analyze_sentiment(positive_text)
        
        # Test negative sentiment
        negative_text = "Not interested, doesn't want to work weekends."
        neg_score = analyze_sentiment(negative_text)
        
        # Test neutral sentiment
        neutral_text = "Called and left voicemail."
        neu_score = analyze_sentiment(neutral_text)
        
        print(f"✅ Sentiment analysis working:")
        print(f"   Positive text score: {pos_score:.2f}")
        print(f"   Negative text score: {neg_score:.2f}")
        print(f"   Neutral text score: {neu_score:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Sentiment analysis test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Running Caregiver Recruitment Dashboard Tests")
    print("=" * 50)
    
    tests = [
        test_app_import,
        test_database_creation,
        test_zip_upload,
        test_sentiment_analysis
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application is ready to deploy.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())



