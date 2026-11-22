"""Data providers.

WeatherProvider   : live Open-Meteo Marine + Forecast APIs (free, no key).
SatelliteProvider : PFZ provider interface for official ISRO MOSDAC / INCOIS /
                    Copernicus / NOAA ERDDAP feeds.
Every failure is returned as unavailable data; fake values are never substituted.
"""
from __future__ import annotations
import datetime as dt
import csv
import json
import math
import ssl
import urllib.parse
import urllib.request
import time
from urllib.error import URLError

import certifi

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ERDDAP_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"
CHL_ERDDAP_URL = "https://coastwatch.noaa.gov/erddap/griddap"


def _build_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


_SSL_CONTEXT = _build_ssl_context()


def _get_json(url: str, params: dict, timeout: float = 6.0) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "ORCA-demo/0.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_text(url: str, timeout: float = 12.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ORCA-marine-advisory/0.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as response:
        return response.read().decode("utf-8-sig")


class WeatherProvider:
    def __init__(self, offline: bool = False, storm: bool = False):
        self.offline = bool(offline)
        self.storm = bool(storm)
        self.last_error = None
        self._cache = {}

    def get(self, lat: float, lon: float) -> dict:
        key = (round(lat, 2), round(lon, 2))
        if key in self._cache:
            return self._cache[key]
        if self.offline:
            data = self._unavailable_weather("Weather provider is offline")
        else:
            try:
                data = self._fetch_live(lat, lon)
            except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
                self.last_error = str(exc)
                data = self._unavailable_weather(str(exc))
        self._cache[key] = data
        return data

    @staticmethod
    def _unavailable_weather(error: str) -> dict:
        return {
            "hours": [],
            "simulated": False,
            "available": False,
            "source": "Open-Meteo Marine + Forecast API (live)",
            "error": error,
        }

    # -- live -----------------------------------------------------------------
    def _fetch_live(self, lat, lon) -> dict:
        marine = _get_json(MARINE_URL, {
            "latitude": lat, "longitude": lon, "forecast_days": 3, "timezone": "auto",
            "hourly": "wave_height,wave_period,wave_direction,swell_wave_height,"
                      "sea_surface_temperature,sea_level_height_msl"})
        fc = _get_json(FORECAST_URL, {
            "latitude": lat, "longitude": lon, "forecast_days": 3, "timezone": "auto",
            "hourly": "wind_speed_10m,wind_gusts_10m,precipitation,weather_code,cape"})
        mh, fh = marine["hourly"], fc["hourly"]
        if all(v is None for v in mh.get("wave_height", [None])):
            raise ValueError("no marine data at this point (land cell?)")
        idx = {t: i for i, t in enumerate(fh["time"])}

        def g(d, k, i):
            v = d.get(k)
            return v[i] if v is not None and i < len(v) else None

        hours = []
        for i, ts in enumerate(mh["time"]):
            j = idx.get(ts)
            hours.append({
                "time": dt.datetime.fromisoformat(ts),
                "wave_height": g(mh, "wave_height", i),
                "wave_period": g(mh, "wave_period", i),
                "swell_height": g(mh, "swell_wave_height", i),
                "sst": g(mh, "sea_surface_temperature", i),
                "sea_level": g(mh, "sea_level_height_msl", i),
                "wind": g(fh, "wind_speed_10m", j) if j is not None else None,
                "gust": g(fh, "wind_gusts_10m", j) if j is not None else None,
                "precip": g(fh, "precipitation", j) if j is not None else None,
                "weather_code": g(fh, "weather_code", j) if j is not None else None,
                "cape": g(fh, "cape", j) if j is not None else None,
            })
        return {"hours": hours, "simulated": False,
                "source": "Open-Meteo Marine + Forecast API (live)"}

class SatelliteProvider:
    """Fetch NOAA near-real-time chlorophyll and SST grids for a PFZ estimate."""

    _cache = {}
    CACHE_TTL_SECONDS = 1800
    CHL_DATASET = "noaacwN20VIIRSchlaDaily"
    CHL_GAP_FILLED_DATASET = "noaacwNPPN20S3ASCIDINEOF2kmDaily"
    SST_DATASET = "ncdcOisst21NrtAgg"
    CHL_SOURCE = "NOAA-20 VIIRS near-real-time chlorophyll (4 km)"
    CHL_GAP_FILLED_SOURCE = "NOAA VIIRS/OLCI gap-filled chlorophyll (2 km)"
    SST_SOURCE = "NOAA NCEI near-real-time OISST (0.25 degree)"

    def get_grid(self, lat, lon, radius_km=150, res=0.1, date=None) -> dict:
        if not -90 < lat < 90 or not -180 <= lon <= 180:
            raise ValueError("PFZ coordinates must be valid latitude/longitude values.")

        cache_key = (round(lat, 2), round(lon, 2), round(radius_km))
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self.CACHE_TTL_SECONDS:
            return cached[1]

        lat_span = radius_km / 111.0
        lon_span = min(180.0, radius_km / (111.0 * max(0.1, math.cos(math.radians(lat)))))
        bounds = (
            max(-89.7, lat - lat_span),
            min(89.7, lat + lat_span),
            max(-179.9, lon - lon_span),
            min(179.9, lon + lon_span),
        )
        sst_url = self._query_url(self.SST_DATASET, "sst", bounds, stride=1, longitude_360=True)
        sst_rows = self._parse_csv(_get_text(sst_url), "sst")

        chlorophyll_source = self.CHL_SOURCE
        chlorophyll_url = self._query_url(
            self.CHL_DATASET, "chlor_a", bounds, stride=4, base_url=CHL_ERDDAP_URL
        )
        chlorophyll_rows = self._parse_csv(_get_text(chlorophyll_url), "chlor_a")
        if not chlorophyll_rows:
            chlorophyll_source = self.CHL_GAP_FILLED_SOURCE
            chlorophyll_url = self._query_url(
                self.CHL_GAP_FILLED_DATASET,
                "chlor_a",
                bounds,
                stride=10,
                base_url=ERDDAP_URL,
            )
            chlorophyll_rows = self._parse_csv(_get_text(chlorophyll_url), "chlor_a")
        if not chlorophyll_rows or not sst_rows:
            raise ValueError("NOAA returned no usable chlorophyll or SST observations for this area.")

        grid = {
            "samples": chlorophyll_rows,
            "sst_samples": sst_rows,
            "source": f"{chlorophyll_source} + {self.SST_SOURCE}",
            "chlorophyll_source": chlorophyll_source,
            "sst_source": self.SST_SOURCE,
            "available": True,
            "simulated": False,
        }
        self._cache[cache_key] = (time.monotonic(), grid)
        return grid

    @staticmethod
    def _query_url(dataset, variable, bounds, stride, longitude_360=False, base_url=ERDDAP_URL):
        lat_min, lat_max, lon_min, lon_max = bounds
        if longitude_360:
            lon_min, lon_max = lon_min % 360, lon_max % 360
            if lon_min > lon_max:
                raise ValueError("NOAA SST grid query cannot cross the antimeridian.")
        query = (
            f"{variable}[(last)][(0)]"
            f"[({lat_min:.4f}):{stride}:({lat_max:.4f})]"
            f"[({lon_min:.4f}):{stride}:({lon_max:.4f})]"
        )
        return f"{base_url}/{dataset}.csv?{urllib.parse.quote(query, safe='(),:')}"

    @staticmethod
    def _parse_csv(content, value_name):
        rows = list(csv.reader(content.splitlines()))
        if len(rows) < 3 or value_name not in rows[0]:
            raise ValueError(f"NOAA response did not contain the expected {value_name} data.")
        columns = {name: index for index, name in enumerate(rows[0])}
        required = ("latitude", "longitude", value_name)
        if any(name not in columns for name in required):
            raise ValueError(f"NOAA response is missing expected {value_name} columns.")

        samples = []
        for row in rows[2:]:
            try:
                sample = {
                    "latitude": float(row[columns["latitude"]]),
                    "longitude": float(row[columns["longitude"]]),
                    value_name: float(row[columns[value_name]]),
                    "time": row[columns["time"]],
                }
            except (IndexError, ValueError, KeyError):
                continue
            if all(math.isfinite(sample[key]) for key in ("latitude", "longitude", value_name)):
                samples.append(sample)
        return samples
