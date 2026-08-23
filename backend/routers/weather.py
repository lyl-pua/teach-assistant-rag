# -*- coding: utf-8 -*-
"""
天气路由（封装 services.weather）
"""
from typing import Optional

from fastapi import APIRouter

from services.weather import get_weather

router = APIRouter(prefix="")


@router.get("/weather")
def weather_endpoint(
    city: Optional[str] = None,
    days: int = 3,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    return get_weather(city=city, lat=lat, lon=lon, days=days)
