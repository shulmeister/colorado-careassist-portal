#!/usr/bin/env python3
"""Check current logo URLs in database"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def check_logos():
    db = db_manager.get_session()
    try:
        tools = db.query(PortalTool).filter(
            PortalTool.name.in_(['EbizCharge', 'Fax.Plus', 'CBI InstaCheck', 'CAPS', 'Google Admin', 'AI Tools', 'RingCentral'])
        ).all()

        for tool in tools:
            print(f"{tool.name}: {tool.icon}")
    finally:
        db.close()

if __name__ == "__main__":
    check_logos()
