from sqlmodel import Session
from app.core.db import engine

def get_session():
    with Session(engine) as session:
        yield session

# For use in scripts that need a direct session instance
SessionLocal = lambda: Session(engine) 