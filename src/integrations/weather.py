"""Real weather integration via Open-Meteo (free, no API key)."""

from __future__ import annotations

import httpx

# Default: Austin, TX
DEFAULT_LAT = 30.2672
DEFAULT_LON = -97.7431

_WEATHER_CODE_MAP: dict[int, str] = {
    0: "Clear",
    1: "Partly cloudy",
    2: "Partly cloudy",
    3: "Partly cloudy",
    45: "Foggy",
    48: "Foggy",
    51: "Rain",
    53: "Rain",
    55: "Rain",
    56: "Rain",
    57: "Rain",
    61: "Rain",
    63: "Rain",
    65: "Rain",
    67: "Rain",
    71: "Snow",
    73: "Snow",
    75: "Snow",
    77: "Snow",
    80: "Showers",
    81: "Showers",
    82: "Showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


def weather_code_to_condition(code: int) -> str:
    """Map an Open-Meteo weather_code to a human-readable condition."""
    return _WEATHER_CODE_MAP.get(code, "Unknown")


async def geocode_location(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[float, float] | None:
    """Geocode a location string via Open-Meteo geocoding API.

    Returns ``(latitude, longitude)`` or ``None`` if not found.
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": query, "count": 1}

    _client = client or httpx.AsyncClient(timeout=10.0)
    own_client = client is None
    try:
        resp = await _client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        if not results:
            return None
        first = results[0]
        return (first["latitude"], first["longitude"])
    except Exception:
        return None
    finally:
        if own_client:
            await _client.aclose()


async def fetch_weather_data(
    latitude: float = DEFAULT_LAT,
    longitude: float = DEFAULT_LON,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch current weather from Open-Meteo.

    Returns a dict with keys: temp, condition, high, low, summary, location.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
        "forecast_days": 1,
    }

    _client = client or httpx.AsyncClient(timeout=10.0)
    own_client = client is None
    try:
        resp = await _client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        daily = data.get("daily", {})
        tz = data.get("timezone", "")

        temp = current.get("temperature_2m", 0)
        code = current.get("weather_code", 0)
        condition = weather_code_to_condition(code)
        high = daily.get("temperature_2m_max", [0])[0]
        low = daily.get("temperature_2m_min", [0])[0]
        location = tz.replace("/", ", ").replace("_", " ")

        summary = f"{condition} in {location}. High of {high} °F, low of {low} °F."

        return {
            "temp": temp,
            "condition": condition,
            "high": high,
            "low": low,
            "summary": summary,
            "location": location,
        }
    except Exception:
        return {
            "temp": 0,
            "condition": "Unknown",
            "high": 0,
            "low": 0,
            "summary": "Weather data unavailable.",
            "location": "Unknown",
            "error": True,
        }
    finally:
        if own_client:
            await _client.aclose()
