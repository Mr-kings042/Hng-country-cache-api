import httpx
import random
from sqlalchemy.ext.asyncio import AsyncSession
from models import Country
from schemas import CountryCreate, CountryResponse
from dotenv import load_dotenv
import os
from logger import get_logger
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
import math
import asyncio
from sqlalchemy import select, func
from pathlib import Path
logger = get_logger(__name__)

load_dotenv()


COUNTRY_API_URL = os.getenv("COUNTRY_API_URL")
EXCHANGE_RATE_API_URL = os.getenv("RATE_API_URL")
class CountryService:
    @staticmethod
    async def fetch_countries_from_api():
       try:
           async with httpx.AsyncClient() as client:
               countries_response = await client.get(COUNTRY_API_URL)
               exchange_rate_response = await client.get(EXCHANGE_RATE_API_URL)
               countries_response.raise_for_status()
               exchange_rate_response.raise_for_status()
               logger.info("Successfully fetched data from APIs")
               countries_data = countries_response.json()
               exchange_rate_data = exchange_rate_response.json()
               return countries_data, exchange_rate_data
       except httpx.HTTPError as e:
           logger.error(f"Error fetching data from API: {e}")
           raise Exception(f"Failed to fetch data from external APIs: {e}")
       

    @staticmethod
    async def refresh_countries(session:AsyncSession):
        try:
            countries_data, exchange_rate_data = await CountryService.fetch_countries_from_api()
        except Exception as e:
            logger.error(f"Failed to refresh countries: {e}")
            raise

        rates = exchange_rate_data.get("rates") if isinstance(exchange_rate_data, dict) else None
        if not rates:
            logger.error("Exchange rates data is missing or invalid")
            rates = {}
        refresh_time = datetime.now(timezone.utc)
        prepared = []
        for c in countries_data:
            name = c.get("name")
            capital = c.get("capital")
            region = c.get("region")
            population = c.get("population")
            flag_url = c.get("flag")
            currencies = c.get("currencies") or []
            currency_code = None
            exchange_rate = None
            estimated_gdp = None

            # If currencies array empty -> currency_code None, exchange_rate None, estimated_gdp 0
            if isinstance(currencies, list) and len(currencies) > 0:
                first = currencies[0]
                # currency objects commonly have 'code'
                currency_code = first.get("code") if isinstance(first, dict) else None
                if currency_code:
                    # lookup exchange rate; rates map currency_code -> rate
                    rate_val = rates.get(currency_code)
                    if rate_val is None:
                        # not found in exchange rates -> exchange_rate None, estimated_gdp None
                        exchange_rate = None
                        estimated_gdp = None
                    else:
                        try:
                            exchange_rate = float(rate_val)
                        except Exception:
                            exchange_rate = None
                        if exchange_rate:
                            # compute estimated_gdp = population × random(1000–2000) ÷ exchange_rate
                            if population:
                                multiplier = random.uniform(1000, 2000)
                                estimated_gdp = (population * multiplier) / exchange_rate
                            else:
                                estimated_gdp = None
                else:
                    # currencies exist but no code on first currency
                    currency_code = None
                    exchange_rate = None
                    estimated_gdp = 0 if not currencies else None
            else:
                # no currencies
                currency_code = None
                exchange_rate = None
                estimated_gdp = 0

            prepared.append({
                "name": name,
                "capital": capital,
                "region": region,
                "population": population,
                "currency_code": currency_code,
                "exchange_rate": exchange_rate,
                "estimated_gdp": estimated_gdp,
                "flag_url": flag_url,
                "last_refreshed_at": refresh_time
            })

        # 2) Upsert into DB in a transaction
        try:
            async with session.begin():
                for rec in prepared:
                    # skip if no name or population missing -> but per requirements name & population & currency_code are required when creating via API;
                    # For refresh we still store countries even with missing currency data, but need name/population for DB model non-null constraints.
                    name = rec["name"]
                    if not name:
                        continue
                    stmt = select(Country).where(func.lower(Country.name) == name.lower())
                    result = await session.execute(stmt)
                    existing = result.scalars().first()
                    if existing:
                        # update fields
                        existing.capital = rec["capital"]
                        existing.region = rec["region"]
                        existing.population = rec["population"] if rec["population"] is not None else existing.population
                        existing.currency_code = rec["currency_code"]
                        existing.exchange_rate = rec["exchange_rate"]
                        # estimated_gdp: if currency_code missing -> 0, if rate missing -> None, else computed
                        existing.estimated_gdp = rec["estimated_gdp"] if rec["estimated_gdp"] is not None else existing.estimated_gdp
                        existing.flag_url = rec["flag_url"]
                        existing.last_refreshed_at = rec["last_refreshed_at"]
                        session.add(existing)
                    else:
                        # create new record; ensure required fields exist or set safe defaults
                        new_country = Country(
                            name=name,
                            capital=rec["capital"],
                            region=rec["region"],
                            population=rec["population"] or 0,
                            currency_code=rec["currency_code"],
                            exchange_rate=rec["exchange_rate"],
                            estimated_gdp=rec["estimated_gdp"] if rec["estimated_gdp"] is not None else (0 if rec["currency_code"] is None else None),
                            flag_url=rec["flag_url"],
                            last_refreshed_at=rec["last_refreshed_at"]
                        )
                        session.add(new_country)
            # commit handled by context manager
        except Exception as e:
            logger.exception("Database error during refresh; rolling back.")
            raise

        # 3) After successful DB save, generate summary image
        await CountryService._generate_summary_image(session, refresh_time)

        return refresh_time

    @staticmethod
    async def _generate_summary_image(session: AsyncSession, refresh_time: datetime):
        """
        Generate a simple summary image at cache/summary.png containing:
        - total number of countries
        - top 5 countries by estimated_gdp
        - timestamp of last refresh
        """
        # fetch stats
        try:
            stmt_total = select(func.count(Country.id))
            total_res = await session.execute(stmt_total)
            total = total_res.scalar() or 0

            # top 5 by estimated_gdp (descending), ignoring nulls
            stmt_top = select(Country).where(Country.estimated_gdp != None).order_by(Country.estimated_gdp.desc()).limit(5)
            top_res = await session.execute(stmt_top)
            top_countries = top_res.scalars().all()
        except Exception:
            logger.exception("Failed to query DB for image generation.")
            return

        # create canvas
        Path("cache").mkdir(parents=True, exist_ok=True)
        img_w, img_h = 800, 600
        bg_color = (30, 30, 30)
        text_color = (240, 240, 240)
        img = Image.new("RGB", (img_w, img_h), color=bg_color)
        draw = ImageDraw.Draw(img)

        try:
            # try to use a common font; fallback if not available
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
            font_body = ImageFont.truetype("DejaVuSans.ttf", 18)
        except Exception:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        padding = 40
        y = padding
        draw.text((padding, y), "Countries Summary", fill=text_color, font=font_title)
        y += 50
        draw.text((padding, y), f"Total countries: {total}", fill=text_color, font=font_body)
        y += 30
        draw.text((padding, y), f"Last refreshed at: {refresh_time.isoformat()}Z", fill=text_color, font=font_body)
        y += 40
        draw.text((padding, y), "Top 5 countries by estimated GDP:", fill=text_color, font=font_body)
        y += 30

        for idx, c in enumerate(top_countries, start=1):
            name = c.name
            gdp = c.estimated_gdp or 0
            draw.text((padding + 10, y), f"{idx}. {name} — {gdp:,.2f}", fill=text_color, font=font_body)
            y += 24

        img_path = Path("cache") / "summary.png"
        try:
            img.save(img_path, format="PNG")
            logger.info(f"Saved summary image to {img_path}")
        except Exception:
            logger.exception("Failed to save summary image.")

country_service = CountryService()