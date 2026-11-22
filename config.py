"""Static configuration: gazetteer, thresholds, illustrative geofences.

NOTE: Thresholds are demo defaults. Align them with official INCOIS / IMD
advisories before any operational use.
"""

APP_NAME = "ORCA"
DEFAULT_QUERY = "Is it safe to go to sea tomorrow morning from Chennai?"
DEFAULT_LOCATION = "chennai"

# ---- Risk thresholds ------------------------------------------------------
WAVE_CAUTION_M = 2.0
WAVE_DANGER_M = 3.0
GUST_CAUTION_KMH = 40.0
GUST_DANGER_KMH = 55.0
CYCLONE_PROXY_GUST_KMH = 75.0
CYCLONE_PROXY_WAVE_M = 4.0

PFZ_RADIUS_KM = 150
PFZ_MIN_SCORE = 0.55
VESSEL_SPEED_KNOTS = 8.0
GEOFENCE_WARN_KM = 30.0
GEOFENCE_AT_BOUNDARY_KM = 5.0

# ---- Gazetteer (nearshore sea points, approximate) -------------------------
# aliases: Latin aliases are matched case-insensitively, native-script aliases by substring.
LOCATIONS = {
    "chennai": {"name": "Chennai", "lat": 13.08, "lon": 80.35,
                "aliases": ["chennai", "madras", "चेन्नई", "சென்னை", "చెన్నై", "চেন্নাই"]},
    "kochi": {"name": "Kochi", "lat": 9.97, "lon": 76.15,
              "aliases": ["kochi", "cochin", "कोच्चि", "கொச்சி", "కొచ్చి", "কোচি"]},
    "visakhapatnam": {"name": "Visakhapatnam", "lat": 17.70, "lon": 83.40,
                      "aliases": ["visakhapatnam", "vizag", "विशाखापत्तनम", "விசாகப்பட்டினம்", "విశాఖపట్నం", "বিশাখাপত্তনম"]},
    "mangaluru": {"name": "Mangaluru", "lat": 12.87, "lon": 74.75,
                  "aliases": ["mangaluru", "mangalore", "मंगलुरु", "மங்களூரு", "మంగళూరు"]},
    "mumbai": {"name": "Mumbai", "lat": 18.90, "lon": 72.75,
               "aliases": ["mumbai", "bombay", "मुंबई", "மும்பை", "ముంబై", "মুম্বাই"]},
    "veraval": {"name": "Veraval", "lat": 20.88, "lon": 70.30,
                "aliases": ["veraval", "वेरावल"]},
    "tuticorin": {"name": "Thoothukudi", "lat": 8.80, "lon": 78.25,
                  "aliases": ["tuticorin", "thoothukudi", "तूतीकोरिन", "தூத்துக்குடி", "తూత్తుకుడి"]},
    "rameswaram": {"name": "Rameswaram", "lat": 9.28, "lon": 79.38,
                   "aliases": ["rameswaram", "rameshwaram", "रामेश्वरम", "ராமேஸ்வரம்", "రామేశ్వరం"]},
    "paradip": {"name": "Paradip", "lat": 20.28, "lon": 86.75,
                "aliases": ["paradip", "paradeep", "पारादीप"]},
    "kanyakumari": {"name": "Kanyakumari", "lat": 8.03, "lon": 77.55,
                    "aliases": ["kanyakumari", "कन्याकुमारी", "கன்னியாகுமரி", "కన్యాకుమారి"]},
    "goa": {"name": "Goa", "lat": 15.42, "lon": 73.75,
            "aliases": ["goa", "गोवा", "கோவா", "గోవా", "গোয়া"]},
    "puducherry": {"name": "Puducherry", "lat": 11.93, "lon": 79.90,
                   "aliases": ["puducherry", "pondicherry", "पुडुचेरी", "புதுச்சேரி", "పుదుచ్చేరి", "পুদুচেরি"]},
    "nagapattinam": {"name": "Nagapattinam", "lat": 10.77, "lon": 79.90,
                     "aliases": ["nagapattinam", "நாகப்பட்டினம்"]},
}

# ---- Geofences (ILLUSTRATIVE PLACEHOLDERS - replace with official data) ----
GEOFENCES = [
    {"name": "India-Sri Lanka IMBL (approx.)", "kind": "international boundary", "type": "line",
     "points": [(10.05, 80.20), (9.55, 79.55), (9.15, 79.35), (8.85, 79.05)],
     "note": "Crossing the International Maritime Boundary Line can lead to arrest."},
    {"name": "India-Pakistan maritime boundary (approx.)", "kind": "international boundary", "type": "line",
     "points": [(23.80, 68.30), (22.50, 67.10), (21.20, 66.40)],
     "note": "Do not cross the boundary; stay on the Indian side."},
    {"name": "Gulf of Mannar Marine National Park (approx.)", "kind": "marine protected area",
     "type": "circle", "center": (9.00, 79.10), "radius_km": 40.0,
     "note": "Fishing is restricted inside the protected area."},
    {"name": "Malvan Marine Sanctuary (approx.)", "kind": "marine protected area",
     "type": "circle", "center": (16.05, 73.45), "radius_km": 12.0,
     "note": "Ecologically sensitive coral/marine habitat."},
    {"name": "Gahirmatha Marine Sanctuary (approx.)", "kind": "ecologically sensitive zone",
     "type": "circle", "center": (20.65, 87.00), "radius_km": 30.0,
     "note": "Olive ridley nesting area; seasonal fishing restrictions apply."},
]
