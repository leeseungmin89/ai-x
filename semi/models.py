from sqlalchemy import Column, Integer, Boolean, Text, String, DateTime
from database import Base
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Date(Base):
    __tablename__ = "date"
    id = Column(Integer, primary_key=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())