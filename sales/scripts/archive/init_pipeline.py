import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, PipelineStage

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Handle Heroku postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_pipeline_stages():
    """Initialize pipeline stages with default values"""
    session = SessionLocal()
    
    try:
        # Check if stages already exist
        existing_stages = session.query(PipelineStage).count()
        
        if existing_stages == 0:
            # Create default stages with order and weighting
            stages = [
                PipelineStage(name="Incoming Leads", order_index=1, weighting=0.10),
                PipelineStage(name="Ongoing Leads", order_index=2, weighting=0.40),
                PipelineStage(name="Pending", order_index=3, weighting=0.80),
                PipelineStage(name="Closed/Won", order_index=4, weighting=1.00),
            ]
            
            session.add_all(stages)
            session.commit()
            print("✅ Pipeline stages initialized successfully!")
            
            for stage in stages:
                print(f"  - {stage.name} (Order: {stage.order_index}, Weight: {stage.weighting * 100}%)")
        else:
            # Update existing stages to add Pending if missing
            incoming = session.query(PipelineStage).filter_by(name="Incoming Leads").first()
            ongoing = session.query(PipelineStage).filter_by(name="Ongoing Leads").first()
            pending = session.query(PipelineStage).filter_by(name="Pending").first()
            closed = session.query(PipelineStage).filter_by(name="Closed/Won").first()
            
            # Set weightings
            if incoming:
                incoming.weighting = 0.10
                incoming.order_index = 1
            if ongoing:
                ongoing.weighting = 0.40
                ongoing.order_index = 2
            if closed:
                closed.weighting = 1.00
                closed.order_index = 4
            
            # Add Pending stage if it doesn't exist
            if not pending:
                pending = PipelineStage(name="Pending", order_index=3, weighting=0.80)
                session.add(pending)
                print("✅ Added 'Pending' stage!")
            else:
                pending.weighting = 0.80
                pending.order_index = 3
            
            session.commit()
            print("✅ Pipeline stages updated successfully!")
            
    except Exception as e:
        print(f"❌ Error initializing pipeline stages: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_pipeline_stages()
