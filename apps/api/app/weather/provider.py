from __future__ import annotations

from datetime import date, datetime

import httpx

from app.weather.normalize import NormalizedForecast, normalize_open_meteo

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES = (
    "precipitation_probability",
    "precipitation",
    "temperature_2m",
    "apparent_temperature",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
)


class WeatherProviderUnavailableError(RuntimeError):
    pass


class OpenMeteoWeatherProvider:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        iana_time_zone: str,
        start_date: date,
        end_date: date,
        fetched_at: datetime,
    ) -> NormalizedForecast:
        try:
            response = self._client.get(
                FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": iana_time_zone,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "hourly": ",".join(HOURLY_VARIABLES),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid provider payload")
            return normalize_open_meteo(payload, fetched_at=fetched_at)
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise WeatherProviderUnavailableError("weather provider unavailable") from error
