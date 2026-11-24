import datetime as dt
from urllib.error import URLError

import pytest

import data_sources
import main
import prompt_engineering
from intent import parse_query
from models import Session
from prompt_engineering import build_prompt, PROMPT_VERSIONS, TEST_INPUTS


def forecast_hours():
    now = dt.datetime.now().replace(minute=0, second=0, microsecond=0)
    hours = []
    for offset in range(72):
        time = now + dt.timedelta(hours=offset)
        next_day_morning = time.date() == (now.date() + dt.timedelta(days=1)) and 5 <= time.hour < 11
        hours.append({
            "time": time,
            "wave_height": 3.2 if next_day_morning else 1.1,
            "wave_period": 8.0,
            "swell_height": 0.6,
            "sst": 29.0,
            "sea_level": None,
            "wind": 35.0 if next_day_morning else 15.0,
            "gust": 57.0 if next_day_morning else 20.0,
            "precip": 0.0,
            "weather_code": 95 if next_day_morning and time.hour == 7 else 0,
            "cape": 400.0,
        })
    return hours


class FakeWeatherProvider:
    def __init__(self, offline=False):
        pass

    def get(self, lat, lon):
        return {
            "hours": forecast_hours(),
            "simulated": False,
            "source": "Test forecast feed",
        }


class FakeSatelliteProvider:
    def __init__(self):
        pass

    def get_grid(self, lat, lon, radius_km=150):
        return {
            "samples": [],
            "sst_samples": [],
            "available": True,
            "simulated": False,
            "source": "NOAA test data",
        }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "WeatherProvider", FakeWeatherProvider)
    monkeypatch.setattr(main, "SatelliteProvider", FakeSatelliteProvider)
    return main.create_app().test_client()


def test_create_app_serves_feature_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"ORCA" in response.data
    assert b"Fishing-zone estimate" in response.data
    assert b"locationSelect" in response.data
    assert b'href="/prompt-lab">Prompt Lab</a>' in response.data
    assert b"Prompt iteration log" not in response.data


@pytest.mark.parametrize(
    ("query", "answer_part"),
    [
        ("What causes ocean tides?", "Moon"),
        ("What are ocean currents?", "seawater"),
        ("How do ocean waves form?", "wind"),
        ("What is marine life?", "food webs"),
        ("Why are coral reefs bleaching?", "bleaching"),
        ("What is salinity?", "Seawater is salty"),
        ("What is a tsunami?", "seafloor"),
        ("What is ocean acidification?", "carbon dioxide"),
        ("How does plastic pollution affect oceans?", "Ocean pollution"),
        ("What is phytoplankton?", "photosynthesis"),
        ("Why is sea level rising?", "sea level"),
        ("What is the ocean?", "Oceans are connected"),
    ],
)
def test_general_ocean_questions_are_answered_without_location(client, query, answer_part):
    response = client.post("/api/analyze", json={"query": query})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["mode"] == "knowledge"
    assert answer_part.lower() in payload["answer"].lower()
    assert payload["location"] is None


def test_local_request_without_location_requests_one(client):
    payload = client.post(
        "/api/analyze", json={"query": "Is it safe to go fishing tomorrow?"}
    ).get_json()

    assert payload["mode"] == "need_location"
    assert payload["location"] is None
    assert "location" in payload["answer"].lower()


def test_selecting_a_location_returns_condition_pfz_and_boundary_details(client):
    response = client.post(
        "/api/analyze",
        json={"query": "Is it safe to fish tomorrow morning?", "location": "chennai"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["mode"] == "advisory"
    assert payload["location"] == "Chennai"
    assert payload["weather"]["status"] == "DANGER"
    assert payload["weather"]["wave"] == 3.2
    assert payload["weather"]["gust"] == 57.0
    assert payload["weather"]["time_range"].endswith("05:00-11:00")
    assert payload["weather"]["alerts"] == [
        "High waves in forecast window",
        "Strong wind gusts in forecast window",
        "Thunderstorm signal in forecast data",
    ]
    assert payload["pfz"]["available"] is False
    assert payload["pfz"]["simulated"] is False
    assert "valid ocean observations" in payload["pfz"]["message"]
    assert len(payload["geofence"]["items"]) > 0
    assert all("distance_km" in item and "near" in item for item in payload["geofence"]["items"])
    assert payload["data_notice"].startswith("Weather is live")


def test_text_location_or_coordinates_are_used(client):
    named = client.post(
        "/api/analyze", json={"query": "Check sea conditions near Kochi"}
    ).get_json()
    coordinates = client.post(
        "/api/analyze", json={"query": "Is the sea safe at 13.08 N, 80.35 E"}
    ).get_json()

    assert named["location"] == "Kochi"
    assert coordinates["location"] == "13.08, 80.35"


def test_boundary_feature_prompt_routes_to_advisory(client):
    payload = client.post(
        "/api/analyze",
        json={"query": "Check nearby coastal boundaries", "location": "kochi"},
    ).get_json()
    assert payload["mode"] == "advisory"
    assert payload["location"] == "Kochi"
    assert payload["geofence"]["items"]
    assert "boundary" in payload["answer"].lower()
    assert "GEOFENCE" in payload["intents"]


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("What are the sea conditions tomorrow?", "CONDITIONS"),
        ("Find a potential fishing zone", "PFZ"),
        ("Are there marine weather alerts?", "ALERTS"),
    ],
)
def test_api_reports_the_requested_feature_intent(client, query, expected_intent):
    payload = client.post(
        "/api/analyze",
        json={"query": query, "location": "chennai"},
    ).get_json()
    assert payload["mode"] == "advisory"
    assert expected_intent in payload["intents"]


def test_coordinate_inside_protected_area_is_identified(client):
    payload = client.post(
        "/api/analyze",
        json={"query": "Check protected boundaries near 9.00, 79.10"},
    ).get_json()
    gulf = next(
        item for item in payload["geofence"]["items"]
        if item["name"].startswith("Gulf of Mannar")
    )
    assert payload["mode"] == "advisory"
    assert gulf["inside"] is True
    assert gulf["distance_km"] == 40.0


def test_explicit_query_location_takes_precedence_over_selector(client):
    payload = client.post(
        "/api/analyze",
        json={"query": "Check weather near Kochi", "location": "chennai"},
    ).get_json()
    assert payload["location"] == "Kochi"


def test_invalid_location_is_rejected(client):
    response = client.post(
        "/api/analyze", json={"query": "Check conditions", "location": "not-a-port"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]


def test_request_with_non_text_query_is_rejected(client):
    response = client.post("/api/analyze", json={"query": ["not", "text"]})
    assert response.status_code == 400


def test_non_object_and_invalid_json_requests_are_rejected(client):
    non_object = client.post("/api/analyze", json=["not", "an", "object"])
    invalid_json = client.post(
        "/api/analyze", data="{", content_type="application/json"
    )
    assert non_object.status_code == 400
    assert invalid_json.status_code == 400


def test_route_optimization_is_not_falsely_reported_as_available(client):
    payload = client.post(
        "/api/analyze",
        json={"query": "Plan a route from Chennai to Kochi"},
    ).get_json()
    assert payload["mode"] == "chat"
    assert "planned" in payload["answer"].lower()


def test_bengali_location_and_advisory_terms_are_recognized():
    parsed = parse_query("চেন্নাই থেকে সমুদ্রে যাওয়া নিরাপদ কি?", Session())
    assert parsed.language == "bn"
    assert parsed.location.name == "Chennai"
    assert "SAFETY" in parsed.intents


def test_weather_provider_reports_unavailable_instead_of_simulated_data(monkeypatch):
    def unavailable(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(data_sources, "_get_json", unavailable)
    provider = data_sources.WeatherProvider()
    result = provider.get(13.08, 80.35)

    assert provider.last_error
    assert result["simulated"] is False
    assert result["available"] is False
    assert result["hours"] == []


def test_satellite_provider_parses_noaa_chlorophyll_and_sst_grids(monkeypatch):
    monkeypatch.setattr(data_sources.SatelliteProvider, "_cache", {})
    responses = iter([
        "time,zlev,latitude,longitude,sst\nUTC,m,degrees_north,degrees_east,degree_C\n"
        "2026-11-18T12:00:00Z,0,13.125,80.375,28.6\n",
        "time,altitude,latitude,longitude,chlor_a\nUTC,m,degrees_north,degrees_east,mg m^-3\n"
        "2026-11-18T00:00:00Z,0,13.1,80.4,1.25\n",
    ])
    urls = []

    def fake_get_text(url, timeout=12.0):
        urls.append(url)
        return next(responses)

    monkeypatch.setattr(data_sources, "_get_text", fake_get_text)
    grid = data_sources.SatelliteProvider().get_grid(13.08, 80.35)

    assert grid["available"] is True
    assert grid["simulated"] is False
    assert grid["samples"][0]["chlor_a"] == 1.25
    assert grid["sst_samples"][0]["sst"] == 28.6
    assert "ncdcOisst21NrtAgg.csv" in urls[0]
    assert "noaacwN20VIIRSchlaDaily.csv" in urls[1]


def test_satellite_provider_uses_gap_filled_chlorophyll_when_nrt_pixels_are_missing(monkeypatch):
    monkeypatch.setattr(data_sources.SatelliteProvider, "_cache", {})
    responses = iter([
        "time,zlev,latitude,longitude,sst\nUTC,m,degrees_north,degrees_east,degree_C\n"
        "2026-11-18T12:00:00Z,0,13.125,80.375,28.6\n",
        "time,altitude,latitude,longitude,chlor_a\nUTC,m,degrees_north,degrees_east,mg m^-3\n"
        "2026-11-15T12:00:00Z,0,13.1,80.4,NaN\n",
        "time,altitude,latitude,longitude,chlor_a\nUTC,m,degrees_north,degrees_east,mg m^-3\n"
        "2026-11-05T12:00:00Z,0,13.1,80.4,1.25\n",
    ])
    urls = []

    def fake_get_text(url, timeout=12.0):
        urls.append(url)
        return next(responses)

    monkeypatch.setattr(data_sources, "_get_text", fake_get_text)
    grid = data_sources.SatelliteProvider().get_grid(13.08, 80.35)

    assert grid["available"] is True
    assert grid["chlorophyll_source"] == data_sources.SatelliteProvider.CHL_GAP_FILLED_SOURCE
    assert grid["samples"][0]["chlor_a"] == 1.25
    assert "noaacwNPPN20S3ASCIDINEOF2kmDaily.csv" in urls[2]


def test_pfz_estimate_uses_observed_chlorophyll_and_sst(monkeypatch):
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    class ObservedSatelliteProvider:
        def __init__(self):
            pass

        def get_grid(self, lat, lon, radius_km=150):
            return {
                "samples": [
                    {"latitude": 13.1, "longitude": 80.6, "chlor_a": 1.2, "time": observed_at},
                    {"latitude": 13.2, "longitude": 81.0, "chlor_a": 2.4, "time": observed_at},
                ],
                "sst_samples": [
                    {"latitude": 13.125, "longitude": 80.625, "sst": 28.4, "time": observed_at},
                    {"latitude": 13.125, "longitude": 81.0, "sst": 28.1, "time": observed_at},
                ],
                "available": True,
                "simulated": False,
                "source": "NOAA observed test data",
            }

    monkeypatch.setattr(main, "SatelliteProvider", ObservedSatelliteProvider)
    result = main._summarize_pfzs(main.Location("Chennai", 13.08, 80.35))

    assert result["available"] is True
    assert result["simulated"] is False
    assert result["latitude"] == 13.2
    assert result["longitude"] == 81.0
    assert result["chl"] == 2.4
    assert result["sst"] == 28.1
    assert "not an official fishing advisory" in result["message"]


@pytest.mark.parametrize(
    ("wave", "gust", "expected"),
    [
        (1.9, 39.9, "SAFE"),
        (2.0, 20.0, "CAUTION"),
        (1.0, 55.0, "DANGER"),
    ],
)
def test_demo_safety_thresholds(wave, gust, expected):
    assert main._safe_level(wave, gust) == expected


def test_empty_message_does_not_run_a_default_location(client):
    payload = client.post("/api/analyze", json={}).get_json()
    assert payload["mode"] == "chat"
    assert payload["location"] is None


def test_prompt_lab_page_and_engineering_evidence(client):
    page = client.get("/prompt-lab")
    evidence = client.get("/api/prompt-engineering").get_json()

    assert page.status_code == 200
    assert b"ORCA Prompt Laboratory" in page.data
    assert len(PROMPT_VERSIONS) >= 3
    assert len(TEST_INPUTS) >= 10
    assert evidence["prompt_versions"][-1]["version"] == "v3"
    assert evidence["model"] == prompt_engineering.MODEL_NAME
    assert "prompt-injection defense" in evidence["techniques"]


def test_zero_shot_and_few_shot_prompts_are_distinct():
    zero_shot = build_prompt("What causes tides?", "zero-shot")
    few_shot = build_prompt("What causes tides?", "few-shot")

    assert "Use no domain examples" in zero_shot["system"]
    assert "Few-shot examples" in few_shot["system"]
    assert "Ignore previous instructions" not in zero_shot["user"]


@pytest.mark.parametrize("strategy", ["zero-shot", "few-shot"])
def test_prompt_run_returns_explicit_unconfigured_status(client, monkeypatch, strategy):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    response = client.post(
        "/api/prompt-run",
        json={"input": "What causes ocean tides?", "strategy": strategy},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["available"] is False
    assert "GEMINI_API_KEY" in payload["answer"]
    assert payload["prompt_version"] == "v3"


def test_gemini_request_uses_verified_certifi_tls_context(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"Tide answer"}]}}]}'

    calls = {}

    def fake_urlopen(req, timeout, context):
        calls["request"] = req
        calls["timeout"] = timeout
        calls["context"] = context
        return FakeResponse()

    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(prompt_engineering.request, "urlopen", fake_urlopen)

    result = prompt_engineering.call_gemini("system", "user")

    assert result["available"] is True
    assert result["answer"] == "Tide answer"
    assert "/models/gemini-3.5-flash-lite:generateContent" in calls["request"].full_url
    assert calls["timeout"] == 30
    assert calls["context"].verify_mode == prompt_engineering.ssl.CERT_REQUIRED
    assert calls["context"].check_hostname is True
