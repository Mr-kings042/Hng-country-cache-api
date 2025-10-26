from fastapi import APIRouter, Depends, HTTPException, Query,status
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Country
from schemas import CountryResponse
from service import country_service
from logger import get_logger
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, func, desc
from datetime import datetime
import os

logger = get_logger(__name__)
router = APIRouter()


@router.post("/countries/refresh",status_code=status.HTTP_201_CREATED)
async def refresh_countries(db: AsyncSession = Depends(get_db)):
    try:
        refresh_time = await country_service.refresh_countries(db)
        return {"message": "Refresh completed", "last_refreshed_at": refresh_time.isoformat() + "Z"}
    except Exception as e:
        # Distinguish external API fetch errors
        msg = str(e)
        logger.error(f"Refresh failed: {msg}")
        return JSONResponse(status_code=503, content={"error": "External data source unavailable", "details": msg})


@router.get("/countries",status_code=status.HTTP_200_OK)
async def list_countries(region: Optional[str] = Query(None), currency: Optional[str] = Query(None), sort: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Country)
        if region:
            stmt = stmt.where(Country.region == region)
        if currency:
            stmt = stmt.where(Country.currency_code == currency)
        if sort == "gdp_desc":
            stmt = stmt.order_by(Country.estimated_gdp.desc().nulls_last())
        result = await db.execute(stmt)
        countries = result.scalars().all()
        # Build explicit JSON structure to match required response format and avoid Pydantic output validation issues.
        output = []
        for c in countries:
            last_iso = None
            if getattr(c, "last_refreshed_at", None):
                try:
                    last_iso = c.last_refreshed_at.isoformat().replace("+00:00", "Z")
                except Exception:
                    last_iso = str(c.last_refreshed_at)

            output.append({
                "id": c.id,
                "name": c.name,
                "capital": c.capital,
                "region": c.region,
                "population": c.population,
                "currency_code": c.currency_code,
                "exchange_rate": float(c.exchange_rate) if c.exchange_rate is not None else None,
                "estimated_gdp": float(c.estimated_gdp) if c.estimated_gdp is not None else None,
                "flag_url": c.flag_url,
                "last_refreshed_at": last_iso
            })

        return output
    except Exception:
        logger.exception("Failed to list countries")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})
@router.get("/countries/image")
async def get_summary_image():
    path = os.path.join("cache", "summary.png")
    if not os.path.exists(path):
        logger.info("Summary image not found at %s", path)
        return JSONResponse(status_code=404, content={"error": "Summary image not found"})
    return FileResponse(path, media_type="image/png")

@router.get("/countries/{name}", response_model=CountryResponse)
async def get_country(name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Country).where(func.lower(Country.name) == name.lower())
    result = await db.execute(stmt)
    country = result.scalars().first()
    if not country:
        return JSONResponse(status_code=404, content={"error": "Country not found"})
    return CountryResponse.model_validate(country)

@router.delete("/countries/{name}")
async def delete_country(name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Country).where(func.lower(Country.name) == name.lower())
    result = await db.execute(stmt)
    country = result.scalars().first()
    if not country:
        return JSONResponse(status_code=404, content={"error": "Country not found"})
    try:
        await db.delete(country)
        await db.commit()
        return {"message": "Country deleted"}
    except Exception:
        logger.exception("Failed to delete country")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})

@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    try:
        total_stmt = select(func.count(Country.id))
        total_res = await db.execute(total_stmt)
        total = total_res.scalar() or 0

        last_stmt = select(func.max(Country.last_refreshed_at))
        last_res = await db.execute(last_stmt)
        last = last_res.scalar()
        last_iso = last.isoformat() + "Z" if last else None
        return {"total_countries": total, "last_refreshed_at": last_iso}
    except Exception:
        logger.exception("Failed to fetch status")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})

