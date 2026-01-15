from portal_database import db_manager
from portal_models import PortalTool
db = db_manager.get_session()
tools = db.query(PortalTool).filter(PortalTool.name.in_(['Google Ads', 'Predis.ai', 'Intuit QuickBooks'])).all()
for t in tools:
    print(f'{t.name}: {t.icon_url}')
db.close()
