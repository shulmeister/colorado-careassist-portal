#!/usr/bin/env python3
"""
Script to create the oauth_tokens table
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from portal_models import Base, OAuthToken

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    exit(1)

# Fix for Heroku postgres:// URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create database engine
engine = create_engine(DATABASE_URL)

try:
    # Create the oauth_tokens table
    print("Creating oauth_tokens table...")
    OAuthToken.__table__.create(engine, checkfirst=True)
    print("✅ Successfully created oauth_tokens table!")
    
except Exception as e:
    print(f"❌ Error: {e}")

