import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = str(Path(__file__).resolve().parent.parent.parent)
sys.path.append(backend_dir)

from sqlmodel import Session, select
from app.db.session import engine
from app.models.api_key import APIKey
from app.core.security import get_password_hash, verify_password

def update_existing_api_keys():
    """Update existing API keys with their hashed versions."""
    with Session(engine) as session:
        # Get all API keys
        query = select(APIKey)
        api_keys = session.exec(query).all()
        
        updated_count = 0
        for api_key in api_keys:
            # Skip if the key is already hashed (doesn't start with "ApiKey ")
            if not api_key.key.startswith("ApiKey "):
                continue
                
            # Hash the existing key
            hashed_key = get_password_hash(api_key.key)
            api_key.key = hashed_key
            updated_count += 1
        
        if updated_count > 0:
            session.commit()
            print(f"Successfully updated {updated_count} API keys with hashed versions")
        else:
            print("No API keys needed updating")

if __name__ == "__main__":
    update_existing_api_keys() 