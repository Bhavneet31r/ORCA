"""Data providers.

WeatherProvider   : live Open-Meteo Marine + Forecast APIs (free, no key), with a
                    deterministic SIMULATED fallback so the demo always runs offline.
SatelliteProvider : synthetic SST / chlorophyll grids. This is the plug-in point for
                    real ISRO MOSDAC / INCOIS PFZ / Copernicus / NOAA ERDDAP feeds.
Everything returned carries `simulated` so the report can label it honestly.
"""
from __future__ import annotations
import datetime as dt
import json
import math
import random
import urllib.parse
import urllib.request

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _get_json(url: str, params: dict, timeout: float = 6.0) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "ORCA-demo/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class WeatherProvider:
    def __init__(self, offline: bool = False, storm: bool = False):
        self.offline = offline or storm      # storm scenario is synthetic by definition
        self.storm = storm
        self._live_ok = not self.offline
        self.last_error = None
        self._cache = {}

    def get(self, lat: float, lon: float) -> dict:
        key = (round(lat, 2), round(lon, 2))
        if key in self._cache:
            return self._cache[key]
        data = None
        if self._live_ok:
            try:
                data = self._fetch_live(lat, lon)
            except Exception as exc:                      # network down, land cell, etc.
                self.last_error = str(exc)
                self._live_ok = False                     # don't keep waiting on timeouts
        if data is None:
            data = self._synthetic(lat, lon)
        self._cache[key] = data
        return data

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

    # -- simulated ------------------------------------------------------------
    def _synthetic(self, lat, lon) -> dict:
        today = dt.date.today()
        start = dt.datetime.combine(today, dt.time(0))
        rng = random.Random(f"wx:{round(lat, 1)}:{round(lon, 1)}:{today}")
        base_wave, base_wind = rng.uniform(0.7, 1.8), rng.uniform(10, 24)
        storm_day = self.storm or rng.random() < 0.2
        s0 = 29 if self.storm else rng.randint(20, 56)      # storm forced for tomorrow morning in demo mode
        phase = lon * 0.05
        sst0 = 30.4 - 0.14 * (lat - 8)
        hours = []
        for h in range(72):
            t = start + dt.timedelta(hours=h)
            wave = base_wave + 0.3 * math.sin(2 * math.pi * (h - 14) / 24) + rng.uniform(-0.1, 0.1)
            wind = base_wind + 4 * math.sin(2 * math.pi * (h - 15) / 24) + rng.uniform(-2, 2)
            code, precip, cape = rng.choice([0, 1, 2, 3]), 0.0, rng.uniform(100, 600)
            if storm_day and s0 <= h < s0 + 10:
                ramp = 1 - abs((h - s0 - 5) / 5)
                wave += 2.0 * ramp + 0.3
                wind += 22 * ramp
                precip, cape = 6 * ramp, 1800 + 800 * ramp
                if ramp > 0.4:
                    code = 95
            hours.append({
                "time": t, "wave_height": round(max(wave, 0.2), 2),
                "wave_period": round(7 + rng.uniform(-1, 1), 1),
                "swell_height": round(max(wave * 0.7, 0.1), 2),
                "sst": round(sst0 + rng.uniform(-0.1, 0.1), 2),
                "sea_level": round(0.8 * math.sin(2 * math.pi * h / 12.42 + phase), 2),
                "wind": round(max(wind, 2), 1), "gust": round(max(wind, 2) * 1.4, 1),
                "precip": round(precip, 1), "weather_code": code, "cape": round(cape),
            })
        label = "SIMULATED marine/weather (storm scenario)" if self.storm else "SIMULATED marine/weather (offline demo)"
        return {"hours": hours, "simulated": True, "source": label}


class SatelliteProvider:
    """Synthetic SST/chlorophyll fields on a lat/lon grid.

    Fields are a function of absolute position + date, so neighbouring queries are
    consistent. Cold-core 'upwelling' blobs raise chlorophyll and create SST fronts,
    which is physically the pattern PFZ advisories look for.

    TODO(real data): replace get_grid() with MOSDAC / INCOIS / Copernicus Marine / ERDDAP.
    """
    name = "SIMULATED satellite SST & chlorophyll grid (plug MOSDAC/INCOIS/Copernicus here)"

    def get_grid(self, lat, lon, radius_km=150, res=0.1, date=None) -> dict:
        date = date or dt.date.today()
        span = radius_km / 111.0
        n = int(2 * span / res) + 1
        lats = [round(lat - span + i * res, 4) for i in range(n)]
        lons = [round(lon - span + j * res, 4) for j in range(n)]
        blobs = []
        for ci in range(math.floor(lats[0]) - 1, math.floor(lats[-1]) + 2):
            for cj in range(math.floor(lons[0]) - 1, math.floor(lons[-1]) + 2):
                rng = random.Random(f"sat:{ci}:{cj}:{date}")
                if rng.random() < 0.6:
                    blobs.append((ci + rng.random(), cj + rng.random(),
                                  rng.uniform(0.15, 0.4), rng.uniform(0.3, 1.0)))
        sst, chl = [], []
        for la in lats:
            srow, crow = [], []
            for lo in lons:
                s = 30.2 - 0.14 * (la - 8) + 0.25 * math.sin(lo * 3.0)
                c = 0.18 + 0.01 * max(0.0, la - 8)
                for (bla, blo, sig, st) in blobs:
                    g = math.exp(-((la - bla) ** 2 + (lo - blo) ** 2) / (2 * sig ** 2))
                    s -= 2.0 * st * g
                    c += 1.8 * st * g
                srow.append(round(s, 2))
                crow.append(round(min(max(c, 0.05), 8.0), 3))
            sst.append(srow)
            chl.append(crow)
        return {"lats": lats, "lons": lons, "sst": sst, "chl": chl,
                "simulated": True, "source": self.name, "date": date}
