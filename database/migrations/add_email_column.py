# add_email_column.py - Migration to add email column to team_members table

import os
import sys
import logging
from sqlalchemy import create_engine, text

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

def add_email_column():
    """Add email column to team_members table"""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Check if email column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'team_members' AND column_name = 'email'
            """)
            
            result = connection.execute(check_query)
            if result.fetchone():
                print("✅ Email column already exists")
                return True
            
            # Add email column
            add_column_query = text("""
                ALTER TABLE team_members 
                ADD COLUMN email VARCHAR(255)
            """)
            
            connection.execute(add_column_query)
            connection.commit()
            
            print("✅ Successfully added email column to team_members table")
            return True
            
    except Exception as e:
        print(f"❌ Error adding email column: {e}")
        return False

if __name__ == "__main__":
    success = add_email_column()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
