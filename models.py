from sqlalchemy import Column, DateTime, Integer, Numeric, String, Float
from sqlalchemy.sql import func
from database import Base

class Country(Base):
    __tablename__ = 'countries'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True, nullable=False)
    capital = Column(String, nullable=True)
    region = Column(String, index=True, nullable=True)
    population = Column(Integer, nullable=False)
    currency_code = Column(String, index=True, nullable=True)
    exchange_rate = Column(Numeric, nullable=True)
    estimated_gdp = Column(Float, nullable=True)
    flag_url = Column(String, nullable=True)
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
