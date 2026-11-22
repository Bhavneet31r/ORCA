"""ORCA marine advisory app.

This is the project entry point: it provides both the command-line demo and the
web UI used for the basic frontend. The underlying marine-analysis logic remains
in the other modules and is reused here.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any
from urllib.error import URLError

from flask import Flask, jsonify, render_template, request

from config import (
    APP_NAME,
    DEFAULT_QUERY,
    GEOFENCE_WARN_KM,
    GEOFENCES,
    GUST_CAUTION_KMH,
    GUST_DANGER_KMH,
    LOCATIONS,
    PFZ_RADIUS_KM,
    VESSEL_SPEED_KNOTS,
    WAVE_CAUTION_M,
    WAVE_DANGER_M,
)
from data_sources import SatelliteProvider, WeatherProvider
from geo_utils import bearing_deg, compass, haversine_km, point_polyline_km
from intent import PART_HOURS, detect_intents, parse_query
from language import LANG_NAMES, t
from models import AnalysisResult, Location, Session
from ocean_knowledge import answer_ocean_question
from prompt_engineering import PROMPT_VERSIONS, TEST_INPUTS, build_prompt, call_gemini


def _safe_level(wave_m: float, gust_kmh: float) -> str:
    if wave_m >= WAVE_DANGER_M or gust_kmh >= GUST_DANGER_KMH:
        return "DANGER"
    if wave_m >= WAVE_CAUTION_M or gust_kmh >= GUST_CAUTION_KMH:
        return "CAUTION"
    return "SAFE"


def _select_forecast_hours(hours: list[dict[str, Any]], parsed) -> list[dict[str, Any]]:
    timed = [hour for hour in hours if isinstance(hour.get("time"), dt.datetime)]
    if not timed:
        return []

    target_date = timed[0]["time"].date() + dt.timedelta(days=parsed.day_offset)
    if parsed.part:
        start_hour, end_hour = PART_HOURS[parsed.part]
    elif parsed.day_offset:
        start_hour, end_hour = 5, 18
    else:
        return timed[:12]

    return [
        hour for hour in timed
        if hour["time"].date() == target_date
        and start_hour <= hour["time"].hour < end_hour
    ]


def _summarize_conditions(loc, parsed) -> dict[str, Any]:
    provider = WeatherProvider(offline=False)
    weather = provider.get(loc.lat, loc.lon)
    hours = _select_forecast_hours(weather.get("hours", []), parsed)
    if not hours:
        return {
            "status": "UNKNOWN",
            "available": weather.get("available", False),
            "wave": None,
            "gust": None,
            "wind": None,
            "period": None,
            "sst": None,
            "rain": None,
            "time_range": parsed.window_label,
            "source": weather.get("source", "n/a"),
            "simulated": weather.get("simulated", False),
            "alerts": [],
        }

    def values(key):
        return [float(hour[key]) for hour in hours if hour.get(key) is not None]

    waves = values("wave_height")
    gusts = values("gust")
    winds = values("wind")
    periods = values("wave_period")
    ssts = values("sst")
    rain = values("precip")
    if not waves and not gusts:
        level = "UNKNOWN"
    else:
        level = _safe_level(max(waves, default=0.0), max(gusts, default=0.0))

    alerts = []
    if max(waves, default=0.0) >= WAVE_DANGER_M:
        alerts.append("High waves in forecast window")
    if max(gusts, default=0.0) >= GUST_DANGER_KMH:
        alerts.append("Strong wind gusts in forecast window")
    if any(hour.get("weather_code") in {95, 96, 99} for hour in hours):
        alerts.append("Thunderstorm signal in forecast data")

    return {
        "status": level,
        "available": True,
        "wave": round(max(waves), 2) if waves else None,
        "wave_average": round(sum(waves) / len(waves), 2) if waves else None,
        "gust": round(max(gusts), 1) if gusts else None,
        "wind": round(max(winds), 1) if winds else None,
        "wind_average": round(sum(winds) / len(winds), 1) if winds else None,
        "period": round(sum(periods) / len(periods), 1) if periods else None,
        "sst": round(sum(ssts) / len(ssts), 1) if ssts else None,
        "rain": round(max(rain), 1) if rain else None,
        "time_range": (
            f"{hours[0]['time']:%d %b %H:%M}-"
            f"{(hours[-1]['time'] + dt.timedelta(hours=1)):%H:%M}"
        ),
        "source": weather.get("source", "n/a"),
        "simulated": weather.get("simulated", False),
        "alerts": alerts,
    }


def _summarize_pfzs(loc) -> dict[str, Any]:
    sat = SatelliteProvider()
    try:
        grid = sat.get_grid(loc.lat, loc.lon, radius_km=PFZ_RADIUS_KM)
    except (URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        return {
            "message": f"Live satellite data could not be loaded: {exc}",
            "source": "NOAA CoastWatch ERDDAP",
            "available": False,
            "simulated": False,
        }
    if not grid.get("available", bool(grid.get("lats"))):
        return {
            "message": grid.get("error", "No live SST / chlorophyll observations are available for this area."),
            "source": grid.get("source", "Official feed not configured"),
            "available": False,
            "simulated": False,
        }
    chlorophyll = grid.get("samples", [])
    sst_samples = grid.get("sst_samples", [])
    candidates = []
    for sample in chlorophyll:
        sst_point = min(
            sst_samples,
            key=lambda point: haversine_km(
                sample["latitude"], sample["longitude"],
                point["latitude"], point["longitude"],
            ),
            default=None,
        )
        if sst_point is None:
            continue
        sst_distance = haversine_km(
            sample["latitude"], sample["longitude"],
            sst_point["latitude"], sst_point["longitude"],
        )
        if sst_distance > 45:
            continue
        distance = haversine_km(loc.lat, loc.lon, sample["latitude"], sample["longitude"])
        if distance <= PFZ_RADIUS_KM and sample["chlor_a"] > 0 and sst_point["sst"] > 0:
            candidates.append({
                "latitude": sample["latitude"],
                "longitude": sample["longitude"],
                "chl": sample["chlor_a"],
                "sst": sst_point["sst"],
                "distance_km": distance,
                "chlorophyll_time": sample["time"],
                "sst_time": sst_point["time"],
            })
    if not candidates:
        return {
            "message": "NOAA has no valid ocean observations within the selected radius.",
            "source": grid["source"],
            "available": False,
            "simulated": False,
        }

    observed_times = [
        dt.datetime.fromisoformat(candidate[key].replace("Z", "+00:00"))
        for candidate in candidates for key in ("chlorophyll_time", "sst_time")
    ]
    latest_observation = max(observed_times)
    observation_age_days = max(0, (dt.datetime.now(dt.timezone.utc) - latest_observation).days)
    if observation_age_days > 21:
        return {
            "message": f"The latest NOAA observation in this area is {latest_observation:%d %b %Y}; it is too old for a current estimate.",
            "source": grid["source"],
            "available": False,
            "simulated": False,
        }

    chlorophyll_scores = [math.log10(candidate["chl"]) for candidate in candidates]
    score_min, score_max = min(chlorophyll_scores), max(chlorophyll_scores)
    for candidate, score in zip(candidates, chlorophyll_scores):
        candidate["score"] = (score - score_min) / (score_max - score_min) if score_max > score_min else 1.0
    best = max(candidates, key=lambda candidate: (candidate["score"], -candidate["distance_km"]))
    d = best["distance_km"]
    brg = bearing_deg(loc.lat, loc.lon, best["latitude"], best["longitude"])
    best["latitude"] = round(best["latitude"], 4)
    best["longitude"] = round(best["longitude"], 4)
    return {
        "distance_km": round(float(d), 1),
        "direction": compass(brg),
        "latitude": best["latitude"],
        "longitude": best["longitude"],
        "estimated_hours_at_8_knots": round(float(d) / (VESSEL_SPEED_KNOTS * 1.852), 1),
        "chl": round(float(best["chl"]), 3),
        "sst": round(float(best["sst"]), 2),
        "score": round(float(best["score"]), 2),
        "observation_date": latest_observation.strftime("%d %b %Y"),
        "observation_age_days": observation_age_days,
        "message": (
            f"Satellite candidate: {d:.1f} km {compass(brg)} of {loc.name}. "
            f"Satellite data are {observation_age_days} days old; this is not an official fishing advisory."
        ),
        "source": grid["source"],
        "available": True,
        "simulated": False,
    }


def _summarize_geofences(loc) -> dict[str, Any]:
    entries = []
    for fence in GEOFENCES:
        name = fence["name"]
        kind = fence["kind"]
        if fence["type"] == "circle":
            cx, cy = fence["center"]
            center_distance = haversine_km(loc.lat, loc.lon, cx, cy)
            inside = center_distance <= fence["radius_km"]
            dist = abs(center_distance - fence["radius_km"])
        else:
            dist = point_polyline_km(loc.lat, loc.lon, fence["points"])
            inside = False
        entries.append({
            "name": name,
            "kind": kind,
            "distance_km": round(float(dist), 1),
            "inside": inside,
            "near": dist <= GEOFENCE_WARN_KM,
            "note": fence["note"],
        })

    return {
        "items": entries,
        "message": "Configured coastal boundaries are approximate reference areas, not an official navigation dataset.",
        "available": True,
        "simulated": False,
    }


def _localized_advisory_answer(
    parsed,
    location: str,
    weather: dict[str, Any],
    pfz: dict[str, Any],
    geofence: dict[str, Any],
) -> str:
    lang = parsed.language
    if "GEOFENCE" in parsed.intents:
        nearest = min(geofence["items"], key=lambda item: item["distance_km"])
        if nearest["inside"]:
            answer = t(
                "g_inside",
                lang,
                zone=nearest["name"],
                kind=nearest["kind"],
                note=nearest["note"],
            )
        elif nearest["near"]:
            answer = t(
                "g_near",
                lang,
                zone=nearest["name"],
                kind=nearest["kind"],
                d=nearest["distance_km"],
            )
        else:
            answer = (
                f"Nearest illustrative boundary/area: {nearest['name']} "
                f"({nearest['distance_km']} km away)."
            )
        answer += "\n" + t("geo_note", lang)
    elif "PFZ" in parsed.intents or "OCEAN" in parsed.intents:
        if pfz.get("available") is False:
            answer = pfz.get("message", "Current satellite data is unavailable, so I cannot estimate a fishing zone.")
        else:
            answer = (
                f"{pfz['message']} Coordinates: {pfz['latitude']}, {pfz['longitude']}. "
                f"Observed chlorophyll: {pfz['chl']} mg/m³; SST: {pfz['sst']} °C "
                f"(observed {pfz['observation_date']}). The estimate uses NOAA satellite data "
                "and is not an official fishing recommendation."
            )
    elif "ALERTS" in parsed.intents:
        signals = weather["alerts"]
        answer = f"Forecast signals for {location} ({weather['time_range']}): "
        answer += "; ".join(signals) if signals else "no automated severe-weather signals detected."
        answer += "\nThese are forecast indicators, not official marine warnings."
    else:
        level = weather["status"]
        level_text = t(f"level_{level}", lang) if level in {"SAFE", "CAUTION", "DANGER"} else level
        if "SAFETY" in parsed.intents:
            answer = t(
                "safety_head",
                lang,
                place=location,
                when=weather["time_range"],
                level=level_text,
            )
            if weather.get("wave") is not None:
                answer += "\n" + t("r_wave", lang, v=weather["wave"])
            if weather.get("gust") is not None:
                answer += "\n" + t("r_gust", lang, v=weather["gust"])
        else:
            answer = t("cond_head", lang, place=location, when=weather["time_range"])
            if weather.get("wave") is not None:
                answer += "\n" + t(
                    "c_wave",
                    lang,
                    mean=weather["wave_average"],
                    max=weather["wave"],
                    per=weather["period"] or "n/a",
                )
            if weather.get("gust") is not None:
                answer += "\n" + t(
                    "c_wind",
                    lang,
                    mean=weather["wind_average"] or "n/a",
                    gust=weather["gust"],
                )
    if lang not in {"en", "hi", "ta", "te"}:
        answer += "\n" + t("lang_fallback", lang, lang=LANG_NAMES.get(lang, lang))
    return answer


def _build_result(query: str, selected_location: str | None = None) -> AnalysisResult:
    session = Session()
    parsed = parse_query(query, session)
    ocean_answer = answer_ocean_question(query)
    if ocean_answer:
        return AnalysisResult(
            status="ok",
            location=None,
            language=parsed.language,
            summary=ocean_answer,
            mode="knowledge",
            answer=ocean_answer,
        )

    if not parsed.intents:
        answer = t("help", parsed.language)
        return AnalysisResult(
            status="ok", location=None, language=parsed.language,
            summary=answer, mode="chat", answer=answer,
        )

    if "ROUTE" in parsed.intents:
        answer = t("deferred", parsed.language)
        return AnalysisResult(
            status="ok", location=None, language=parsed.language,
            summary=answer, mode="chat", answer=answer,
        )

    loc = parsed.location
    if loc is None and selected_location in LOCATIONS:
        item = LOCATIONS[selected_location]
        loc = Location(item["name"], item["lat"], item["lon"])

    if loc is None:
        answer = t("need_location", parsed.language)
        return AnalysisResult(
            status="warning",
            location=None,
            language=parsed.language,
            summary=answer,
            mode="need_location",
            answer=answer,
        )

    weather = _summarize_conditions(loc, parsed)
    pfz = _summarize_pfzs(loc)
    geofence = _summarize_geofences(loc)
    status = "warning" if weather["status"] in {"CAUTION", "DANGER", "UNKNOWN"} else "ok"
    summary = f"{loc.name}: {weather['status']} conditions for {weather['time_range']}."
    if weather["wave"] is not None:
        summary += f" Maximum wave {weather['wave']} m."
    if weather["gust"] is not None:
        summary += f" Maximum gust {weather['gust']} km/h."
    answer = _localized_advisory_answer(parsed, loc.name, weather, pfz, geofence)

    return AnalysisResult(
        status=status,
        location=loc.name,
        language=parsed.language,
        weather=weather,
        pfz=pfz,
        geofence=geofence,
        summary=summary,
        timestamp=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        mode="advisory",
        answer=answer,
    )


def demo_query(query: str | None = None) -> str:
    if query is None:
        query = DEFAULT_QUERY
    result = _build_result(query)
    return (
        f"Location: {result.location}\n"
        f"Status: {result.status}\n"
        f"Weather: {result.weather}\n"
        f"PFZ: {result.pfz}\n"
        f"Geofence: {result.geofence}\n"
        f"Summary: {result.summary}"
    )


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        locations = sorted(
            ((key, value["name"]) for key, value in LOCATIONS.items()),
            key=lambda item: item[1],
        )
        return render_template(
            "index.html",
            app_name=APP_NAME,
            locations=locations,
        )

    @app.get("/prompt-lab")
    def prompt_lab():
        return render_template(
            "prompt_lab.html",
            app_name=APP_NAME,
            prompt_versions=PROMPT_VERSIONS,
            test_inputs=TEST_INPUTS,
        )

    @app.post("/api/prompt-run")
    def prompt_run():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        user_input = payload.get("input", "")
        strategy = payload.get("strategy", "few-shot")
        context = payload.get("context", "")
        if not isinstance(user_input, str) or not user_input.strip():
            return jsonify({"error": "Enter a prompt test input."}), 400
        if not isinstance(context, str):
            return jsonify({"error": "Context must be text."}), 400
        if strategy not in {"zero-shot", "few-shot"}:
            return jsonify({"error": "Strategy must be zero-shot or few-shot."}), 400

        prompt = build_prompt(user_input, strategy, context)
        result = call_gemini(prompt["system"], prompt["user"])
        return jsonify({
            "status": "ok",
            "strategy": strategy,
            "prompt_version": PROMPT_VERSIONS[-1]["version"],
            "system_prompt": prompt["system"],
            "user_prompt": prompt["user"],
            **result,
        })

    @app.get("/api/prompt-engineering")
    def prompt_engineering_data():
        return jsonify({
            "prompt_versions": PROMPT_VERSIONS,
            "test_inputs": TEST_INPUTS,
            "model": "Gemini 2.5 Flash",
            "model_configured": bool(
                __import__("os").getenv("GEMINI_API_KEY")
                or __import__("os").getenv("GOOGLE_API_KEY")
            ),
            "techniques": ["zero-shot prompting", "few-shot prompting", "role prompting",
                           "structured output", "prompt-injection defense", "uncertainty handling"],
        })

    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "Request body must be valid JSON."}), 400
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        raw_query = payload.get("query")
        if raw_query is None:
            raw_query = payload.get("text", "")
        if not isinstance(raw_query, str):
            return jsonify({"error": "The query must be text."}), 400
        selected_location = payload.get("location")
        if selected_location and (
            not isinstance(selected_location, str) or selected_location not in LOCATIONS
        ):
            return jsonify({"error": "Choose a supported coastal location."}), 400
        result = _build_result(raw_query.strip(), selected_location)
        return jsonify(
            {
                "status": result.status,
                "mode": result.mode,
                "intents": detect_intents(raw_query.lower()),
                "answer": result.answer or result.summary,
                "location": result.location,
                "language": result.language,
                "summary": result.summary,
                "weather": result.weather,
                "pfz": result.pfz,
                "geofence": result.geofence,
                "timestamp": result.timestamp,
                "data_notice": (
                    "Weather is live forecast data; it is not an official safety advisory."
                    if result.weather.get("available")
                    else "Live weather data is unavailable; no synthetic forecast values are shown."
                ) if result.mode == "advisory" else "",
            }
        )

    return app


def main() -> None:
    app = create_app()
    app.run(debug=False, host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
