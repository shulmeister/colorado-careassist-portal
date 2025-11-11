"""
Update Sales Dashboard and Recruitment Dashboard tiles to use internal routes
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    # Update Sales Dashboard to use internal route
    sales_dashboard = db.query(PortalTool).filter(
        PortalTool.name == "Sales Dashboard"
    ).first()
    
    if sales_dashboard:
        old_url = sales_dashboard.url
        sales_dashboard.url = "/sales"
        print(f"✅ Updated Sales Dashboard:")
        print(f"   Old URL: {old_url}")
        print(f"   New URL: /sales")
    else:
        # Create if doesn't exist
        sales_dashboard = PortalTool(
            name="Sales Dashboard",
            url="/sales",
            icon="📊",
            description="View sales metrics, visits, and analytics",
            category="Analytics",
            display_order=1,
            is_active=True
        )
        db.add(sales_dashboard)
        print(f"✅ Created Sales Dashboard tile pointing to /sales")
    
    # Check if Recruitment Dashboard exists
    recruitment_dashboard = db.query(PortalTool).filter(
        PortalTool.name == "Recruitment Dashboard"
    ).first()
    
    if recruitment_dashboard:
        old_url = recruitment_dashboard.url
        recruitment_dashboard.url = "/recruitment"
        print(f"✅ Updated Recruitment Dashboard:")
        print(f"   Old URL: {old_url}")
        print(f"   New URL: /recruitment")
    else:
        # Create Recruitment Dashboard tile
        recruitment_dashboard = PortalTool(
            name="Recruitment Dashboard",
            url="/recruitment",
            icon="👥",
            description="Manage recruitment and hiring pipeline",
            category="Analytics",
            display_order=2,
            is_active=True
        )
        db.add(recruitment_dashboard)
        print(f"✅ Created Recruitment Dashboard tile pointing to /recruitment")
    
    db.commit()
    print(f"\n🎯 Dashboard tiles successfully updated!")
    
    # Show updated tools
    dashboards = db.query(PortalTool).filter(
        PortalTool.name.in_(["Sales Dashboard", "Recruitment Dashboard"])
    ).all()
    
    print(f"\n📊 Dashboard Tools:")
    for tool in dashboards:
        print(f"   {tool.icon} {tool.name} → {tool.url}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

