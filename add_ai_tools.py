#!/usr/bin/env python3
"""Add AI Tools to database"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
try:
    existing = db.query(PortalTool).filter(PortalTool.name == "AI Tools").first()
    if existing:
        print("✅ AI Tools already exists")
    else:
        max_order = db.query(PortalTool).order_by(PortalTool.display_order.desc()).first()
        next_order = (max_order.display_order + 1) if max_order else 24
        
        tool = PortalTool(
            name="AI Tools",
            url="#ai-tools-dropdown",
            icon="🤖",
            description="AI assistant tools",
            category="AI",
            display_order=next_order,
            is_active=True
        )
        db.add(tool)
        db.commit()
        print("✅ Added AI Tools")
finally:
    db.close()

