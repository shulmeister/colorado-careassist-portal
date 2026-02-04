#!/usr/bin/env python3
"""
Script to add the Data Connections tile to the portal database.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from portal_models import PortalTool

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    exit(1)

# Fix for Mac Mini (Local) postgres:// URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create database engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Check if Connections tile already exists
    existing_tool = session.query(PortalTool).filter(PortalTool.name == "Data Connections").first()
    
    if existing_tool:
        print("✓ Data Connections tile already exists")
        print(f"  ID: {existing_tool.id}")
        print(f"  Name: {existing_tool.name}")
        print(f"  URL: {existing_tool.url}")
    else:
        # Create new Connections tile
        new_tool = PortalTool(
            name="Data Connections",
            description="Manage API connections and data sources",
            url="/connections",
            icon="/static/icons/connections-icon.svg",
            category="settings"
        )
        
        session.add(new_tool)
        session.commit()
        
        print("✅ Successfully added Data Connections tile!")
        print(f"  ID: {new_tool.id}")
        print(f"  Name: {new_tool.name}")
        print(f"  URL: {new_tool.url}")
        print(f"  Icon: {new_tool.icon}")
        print(f"  Category: {new_tool.category}")

except Exception as e:
    print(f"❌ Error: {e}")
    session.rollback()
finally:
    session.close()

