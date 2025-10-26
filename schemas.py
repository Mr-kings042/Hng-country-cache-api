from datetime import datetime
import random
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional

class CountryBase(BaseModel):
    # Required by project: name and population are required.
    name: str = Field(..., example="Nigeria")
    capital: Optional[str] = Field(None, example="Abuja")
    region: Optional[str] = Field(None, example="Africa")
    population: int = Field(..., gt=0, description="The population of the country", example=200000000)
    currency_code: Optional[str] = Field(None, description="The currency code of the country", example="NGN")
    exchange_rate: Optional[float] = Field(None, gt=0, description="The exchange rate of the currency", example=410.0)
    flag_url: Optional[str] = Field(None, description="The URL of the country's flag")

    
    @field_validator("name", "population", mode="before")
    def validate_required_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field.name}: is required")
        return value

class CountryCreate(CountryBase):
   
    estimated_gdp: Optional[float] = Field(None, gt=0, description="The estimated GDP of the country", example=450000000000)

    @model_validator(mode="after")
    def compute_estimated_gdp(self):
      
        if getattr(self, "population", None) and getattr(self, "exchange_rate", None):
            try:
                multiplier = random.uniform(1000, 2000)
                self.estimated_gdp = (self.population * multiplier) / float(self.exchange_rate)
            except Exception:
                self.estimated_gdp = None
        else:
            self.estimated_gdp = self.estimated_gdp
        return self

class CountryResponse(CountryBase):
    id: int
    last_refreshed_at: Optional[datetime] = Field(None, description="The last time the country data was refreshed")
    model_config = {"from_attributes": True}
