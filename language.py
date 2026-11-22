"""Language detection (by script) and localized response templates.

Responses are fully localized for: en, hi, ta, te.
Other Indian scripts are detected; replies fall back to English with a note.
"""
from __future__ import annotations

_SCRIPT_RANGES = [
    ("hi", 0x0900, 0x097F),   # Devanagari (Hindi/Marathi) -> Hindi
    ("bn", 0x0980, 0x09FF),
    ("pa", 0x0A00, 0x0A7F),
    ("gu", 0x0A80, 0x0AFF),
    ("or", 0x0B00, 0x0B7F),
    ("ta", 0x0B80, 0x0BFF),
    ("te", 0x0C00, 0x0C7F),
    ("kn", 0x0C80, 0x0CFF),
    ("ml", 0x0D00, 0x0D7F),
]
LANG_NAMES = {"en": "English", "hi": "Hindi", "bn": "Bengali", "pa": "Punjabi", "gu": "Gujarati",
              "or": "Odia", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam"}
SUPPORTED = {"en", "hi", "ta", "te"}


def detect_language(text: str) -> str:
    counts = {}
    for ch in text:
        cp = ord(ch)
        for code, lo, hi in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    return max(counts, key=counts.get) if counts else "en"


def _t(en, hi, ta, te):
    return {"en": en, "hi": hi, "ta": ta, "te": te}


TR = {
    "level_SAFE": _t("SAFE", "सुरक्षित", "பாதுகாப்பானது", "సురక్షితం"),
    "level_CAUTION": _t("CAUTION", "सावधानी", "எச்சரிக்கை", "జాగ్రత్త"),
    "level_DANGER": _t("DANGEROUS", "खतरनाक", "ஆபத்தானது", "ప్రమాదకరం"),
    "loc_used": _t("Location: {place}", "स्थान: {place}", "இடம்: {place}", "ప్రదేశం: {place}"),
    "safety_head": _t("Sea safety for {place} ({when}): {level}",
                      "{place} के लिए समुद्री सुरक्षा ({when}): {level}",
                      "{place} கடல் பாதுகாப்பு ({when}): {level}",
                      "{place} సముద్ర భద్రత ({when}): {level}"),
    "risk_index": _t("Risk index: {v}/100", "जोखिम सूचकांक: {v}/100",
                     "அபாய குறியீடு: {v}/100", "ప్రమాద సూచిక: {v}/100"),
    "r_wave": _t("Waves up to {v} m", "लहरें {v} मीटर तक", "அலைகள் {v} மீ வரை", "అలలు {v} మీ వరకు"),
    "r_gust": _t("Wind gusts up to {v} km/h", "हवा के झोंके {v} किमी/घंटा तक",
                 "காற்று வேகம் {v} கிமீ/மணி வரை", "గాలి వేగం {v} కిమీ/గం వరకు"),
    "r_storm": _t("Thunderstorm / lightning risk", "आंधी-तूफान/बिजली का खतरा",
                  "இடி மின்னல் அபாயம்", "ఉరుములు/పిడుగుల ప్రమాదం"),
    "r_cyclone": _t("Possible cyclonic / squally conditions", "चक्रवात जैसी स्थिति की संभावना",
                    "புயல் போன்ற சூழல் வாய்ப்பு", "తుఫాను వంటి పరిస్థితులకు అవకాశం"),
    "r_ok": _t("Waves and winds are within safe limits", "लहरें और हवा सुरक्षित सीमा में हैं",
               "அலைகளும் காற்றும் பாதுகாப்பான அளவில் உள்ளன", "అలలు, గాలి సురక్షిత పరిమితుల్లో ఉన్నాయి"),
    "rec_SAFE": _t("Conditions look suitable for fishing. Keep checking for updates.",
                   "मछली पकड़ने के लिए स्थितियाँ अनुकूल हैं। अपडेट देखते रहें।",
                   "மீன்பிடிக்க நிலைமை சாதகமாக உள்ளது. புதுப்பிப்புகளைக் கவனியுங்கள்.",
                   "చేపల వేటకు పరిస్థితులు అనుకూలంగా ఉన్నాయి. అప్‌డేట్‌లను గమనించండి."),
    "rec_CAUTION": _t("Go only if necessary, stay close to shore and carry safety gear.",
                      "बहुत ज़रूरी हो तभी जाएँ, किनारे के पास रहें और सुरक्षा उपकरण रखें।",
                      "அவசியம் என்றால் மட்டுமே செல்லுங்கள்; கரையருகே இருங்கள், பாதுகாப்பு உபகரணங்களை வைத்திருங்கள்.",
                      "తప్పనిసరైతేనే వెళ్లండి; తీరానికి దగ్గరగా ఉండండి, భద్రతా పరికరాలు తీసుకెళ్లండి."),
    "rec_DANGER": _t("Do not venture into the sea. Wait for conditions to improve.",
                     "समुद्र में न जाएँ। स्थिति सुधरने तक प्रतीक्षा करें।",
                     "கடலுக்குச் செல்ல வேண்டாம். நிலைமை சீராகும் வரை காத்திருங்கள்.",
                     "సముద్రంలోకి వెళ్లవద్దు. పరిస్థితి మెరుగయ్యే వరకు వేచి ఉండండి."),
    "pfz_head": _t("Nearest Potential Fishing Zone: {d} km {dir} of {place} (lat {lat}, lon {lon})",
                   "{place} से सबसे नज़दीकी संभावित मछली पकड़ने का क्षेत्र: {dir} दिशा में {d} किमी (अक्षांश {lat}, देशांतर {lon})",
                   "{place}-இல் இருந்து அருகிலுள்ள சாத்தியமான மீன்பிடி மண்டலம்: {dir} திசையில் {d} கிமீ (அட்சரேகை {lat}, தீர்க்கரேகை {lon})",
                   "{place} నుండి సమీప సంభావ్య చేపల వేట ప్రాంతం: {dir} దిశలో {d} కిమీ (అక్షాంశం {lat}, రేఖాంశం {lon})"),
    "pfz_why": _t("Why: chlorophyll {chl} mg/m³, SST {sst} °C, temperature front {front} °C/10 km, score {score}",
                  "कारण: क्लोरोफिल {chl} mg/m³, समुद्री सतह तापमान {sst} °C, तापमान फ्रंट {front} °C/10 किमी, स्कोर {score}",
                  "காரணம்: குளோரோபில் {chl} mg/m³, கடல் மேற்பரப்பு வெப்பநிலை {sst} °C, வெப்பநிலை முகப்பு {front} °C/10 கிமீ, மதிப்பெண் {score}",
                  "కారణం: క్లోరోఫిల్ {chl} mg/m³, సముద్ర ఉపరితల ఉష్ణోగ్రత {sst} °C, ఉష్ణోగ్రత ఫ్రంట్ {front} °C/10 కిమీ, స్కోరు {score}"),
    "pfz_eta": _t("About {h} h sailing at {kn} knots", "{kn} नॉट पर लगभग {h} घंटे",
                  "{kn} நாட் வேகத்தில் சுமார் {h} மணி", "{kn} నాట్ల వేగంతో సుమారు {h} గంటలు"),
    "pfz_safety": _t("Conditions at that PFZ: {level}", "उस PFZ पर स्थिति: {level}",
                     "அந்த PFZ-இல் நிலை: {level}", "ఆ PFZ వద్ద పరిస్థితి: {level}"),
    "pfz_none": _t("No strong PFZ found within {r} km.", "{r} किमी के भीतर कोई मज़बूत PFZ नहीं मिला।",
                   "{r} கிமீ சுற்றளவில் வலுவான PFZ இல்லை.", "{r} కిమీ పరిధిలో బలమైన PFZ కనబడలేదు."),
    "cond_head": _t("Sea & weather near {place} ({when})", "{place} के पास समुद्र और मौसम ({when})",
                    "{place} அருகே கடல் & வானிலை ({when})", "{place} సమీపంలో సముద్రం & వాతావరణం ({when})"),
    "c_wave": _t("Waves: {mean} m avg, {max} m max (period {per} s)",
                 "लहरें: औसत {mean} मी, अधिकतम {max} मी (अवधि {per} से)",
                 "அலைகள்: சராசரி {mean} மீ, அதிகபட்சம் {max} மீ (காலம் {per} வி)",
                 "అలలు: సగటు {mean} మీ, గరిష్టం {max} మీ (వ్యవధి {per} సె)"),
    "c_wind": _t("Wind: {mean} km/h avg, gusts {gust} km/h",
                 "हवा: औसत {mean} किमी/घंटा, झोंके {gust} किमी/घंटा",
                 "காற்று: சராசரி {mean} கிமீ/மணி, அதிகபட்சம் {gust} கிமீ/மணி",
                 "గాలి: సగటు {mean} కిమీ/గం, గరిష్టం {gust} కిమీ/గం"),
    "c_sst": _t("Sea surface temperature: {sst} °C", "समुद्री सतह तापमान: {sst} °C",
                "கடல் மேற்பரப்பு வெப்பநிலை: {sst} °C", "సముద్ర ఉపరితల ఉష్ణోగ్రత: {sst} °C"),
    "c_tide": _t("Tide: high {high}; low {low}", "ज्वार: उच्च {high}; निम्न {low}",
                 "ஓதம்: உயர் {high}; தாழ் {low}", "ఆటుపోట్లు: అధికం {high}; తక్కువ {low}"),
    "c_tide_na": _t("Tide: data unavailable", "ज्वार: डेटा उपलब्ध नहीं", "ஓதம்: தரவு இல்லை", "ఆటుపోట్లు: డేటా లేదు"),
    "c_rain": _t("Rain: up to {r} mm/h", "बारिश: {r} मिमी/घंटा तक", "மழை: {r} மிமீ/மணி வரை", "వర్షం: {r} మిమీ/గం వరకు"),
    "a_head": _t("Alerts for {place} (next 48 h)", "{place} के लिए चेतावनियाँ (अगले 48 घंटे)",
                 "{place} எச்சரிக்கைகள் (அடுத்த 48 மணி)", "{place} హెచ్చరికలు (తదుపరి 48 గంటలు)"),
    "a_none": _t("No alerts in the next 48 h.", "अगले 48 घंटों में कोई चेतावनी नहीं।",
                 "அடுத்த 48 மணி நேரத்தில் எச்சரிக்கை இல்லை.", "తదుపరి 48 గంటల్లో హెచ్చరికలు లేవు."),
    "a_wave": _t("High waves: up to {v} m around {t}", "ऊँची लहरें: {t} के आसपास {v} मीटर तक",
                 "உயர் அலைகள்: {t} அளவில் {v} மீ வரை", "ఎత్తైన అలలు: {t} సమయంలో {v} మీ వరకు"),
    "a_wind": _t("Strong winds: gusts up to {v} km/h around {t}", "तेज़ हवा: {t} के आसपास {v} किमी/घंटा तक",
                 "பலத்த காற்று: {t} அளவில் {v} கிமீ/மணி வரை", "బలమైన గాలులు: {t} సమయంలో {v} కిమీ/గం వరకు"),
    "a_storm": _t("Thunderstorm / lightning possible around {t}", "{t} के आसपास आंधी-तूफान/बिजली की संभावना",
                  "{t} அளவில் இடி மின்னல் வாய்ப்பு", "{t} సమయంలో ఉరుములు/పిడుగులు పడే అవకాశం"),
    "a_cyclone": _t("Possible cyclonic / squally conditions around {t}. Check the official IMD cyclone bulletin.",
                    "{t} के आसपास चक्रवात जैसी स्थिति संभव। IMD का आधिकारिक बुलेटिन देखें।",
                    "{t} அளவில் புயல் போன்ற சூழல் வாய்ப்பு. IMD அதிகாரப்பூர்வ அறிவிப்பைப் பாருங்கள்.",
                    "{t} సమయంలో తుఫాను వంటి పరిస్థితులు సాధ్యం. IMD అధికారిక బులెటిన్ చూడండి."),
    "o_head": _t("Chlorophyll & SST around {place}", "{place} के आसपास क्लोरोफिल और SST",
                 "{place} சுற்றிலும் குளோரோபில் & SST", "{place} చుట్టూ క్లోరోఫిల్ & SST"),
    "o_line": _t("Favourable area (chl ≥ 0.5 mg/m³ and SST 26–30 °C): {pct}%",
                 "अनुकूल क्षेत्र (chl ≥ 0.5 mg/m³ और SST 26–30 °C): {pct}%",
                 "சாதகமான பகுதி (chl ≥ 0.5 mg/m³ மற்றும் SST 26–30 °C): {pct}%",
                 "అనుకూల ప్రాంతం (chl ≥ 0.5 mg/m³ మరియు SST 26–30 °C): {pct}%"),
    "o_best": _t("Best patch: {d} km {dir} (lat {lat}, lon {lon}), chl {chl} mg/m³, SST {sst} °C",
                 "सबसे अच्छा क्षेत्र: {dir} दिशा में {d} किमी (अक्षांश {lat}, देशांतर {lon}), chl {chl} mg/m³, SST {sst} °C",
                 "சிறந்த பகுதி: {dir} திசையில் {d} கிமீ (அட்சரேகை {lat}, தீர்க்கரேகை {lon}), chl {chl} mg/m³, SST {sst} °C",
                 "ఉత్తమ ప్రాంతం: {dir} దిశలో {d} కిమీ (అక్షాంశం {lat}, రేఖాంశం {lon}), chl {chl} mg/m³, SST {sst} °C"),
    "o_mean": _t("Area mean: chl {chl} mg/m³, SST {sst} °C", "क्षेत्र औसत: chl {chl} mg/m³, SST {sst} °C",
                 "பகுதி சராசரி: chl {chl} mg/m³, SST {sst} °C", "ప్రాంత సగటు: chl {chl} mg/m³, SST {sst} °C"),
    "o_none": _t("No favourable chlorophyll/SST patch found.", "कोई अनुकूल क्लोरोफिल/SST क्षेत्र नहीं मिला।",
                 "சாதகமான குளோரோபில்/SST பகுதி இல்லை.", "అనుకూల క్లోరోఫిల్/SST ప్రాంతం కనబడలేదు."),
    "g_head": _t("Geofence check", "जियोफेंस जाँच", "ஜியோஃபென்ஸ் சோதனை", "జియోఫెన్స్ తనిఖీ"),
    "g_clear": _t("No restricted boundary or protected area within {r} km.",
                  "{r} किमी के भीतर कोई प्रतिबंधित सीमा या संरक्षित क्षेत्र नहीं।",
                  "{r} கிமீ சுற்றளவில் தடைசெய்யப்பட்ட எல்லை/பாதுகாக்கப்பட்ட பகுதி இல்லை.",
                  "{r} కిమీ పరిధిలో నిషేధిత సరిహద్దు/రక్షిత ప్రాంతం లేదు."),
    "g_inside": _t("INSIDE {zone} ({kind}). {note}", "{zone} ({kind}) के भीतर हैं। {note}",
                   "{zone} ({kind}) உள்ளே உள்ளீர்கள். {note}", "{zone} ({kind}) లోపల ఉన్నారు. {note}"),
    "g_at": _t("AT BOUNDARY: {zone} ({kind}) is {d} km away. {note}", "सीमा पर: {zone} ({kind}) केवल {d} किमी दूर। {note}",
               "எல்லையில்: {zone} ({kind}) {d} கிமீ தொலைவில். {note}", "సరిహద్దు వద్ద: {zone} ({kind}) {d} కిమీ దూరంలో. {note}"),
    "g_near": _t("Approaching {zone} ({kind}): {d} km away.", "{zone} ({kind}) के पास: {d} किमी दूर।",
                 "{zone} ({kind}) அருகில்: {d} கிமீ தொலைவில்.", "{zone} ({kind}) సమీపంలో: {d} కిమీ దూరంలో."),
    "geo_note": _t("Note: geofence boundaries in this demo are illustrative; load official boundary data before real use.",
                   "नोट: इस डेमो में जियोफेंस सीमाएँ केवल उदाहरण हैं; वास्तविक उपयोग से पहले आधिकारिक सीमा डेटा लोड करें।",
                   "குறிப்பு: இந்த டெமோவில் உள்ள எல்லைகள் எடுத்துக்காட்டு மட்டுமே; உண்மையான பயன்பாட்டிற்கு முன் அதிகாரப்பூர்வ தரவை ஏற்றவும்.",
                   "గమనిక: ఈ డెమోలోని సరిహద్దులు ఉదాహరణ మాత్రమే; నిజమైన వినియోగానికి ముందు అధికారిక డేటాను లోడ్ చేయండి."),
    "sim_note": _t("Note: items marked [simulated] are demo data because live feeds were unavailable.",
                   "नोट: [simulated] चिह्नित डेटा डेमो डेटा है क्योंकि लाइव फ़ीड उपलब्ध नहीं थे।",
                   "குறிப்பு: [simulated] எனக் குறிக்கப்பட்டவை லைவ் தரவு இல்லாததால் டெமோ தரவு.",
                   "గమనిక: [simulated] గుర్తు ఉన్నవి లైవ్ డేటా లేనందున డెమో డేటా."),
    "evid_head": _t("Evidence", "प्रमाण", "ஆதாரம்", "ఆధారాలు"),
    "need_location": _t("Please tell me your location (port/village name, or latitude, longitude like 13.08, 80.35).",
                        "कृपया अपना स्थान बताएँ (बंदरगाह/गाँव का नाम, या अक्षांश, देशांतर जैसे 13.08, 80.35)।",
                        "உங்கள் இடத்தைத் தெரிவிக்கவும் (துறைமுகம்/ஊர் பெயர், அல்லது 13.08, 80.35 போன்ற அட்சரேகை, தீர்க்கரேகை).",
                        "మీ ప్రదేశం చెప్పండి (ఓడరేవు/గ్రామం పేరు, లేదా 13.08, 80.35 వంటి అక్షాంశం, రేఖాంశం)."),
    "help": _t("I can help with: Potential Fishing Zones, sea safety, tide/weather/sea conditions, cyclone/lightning alerts, "
               "chlorophyll & SST, and boundary (geofence) checks. Example: 'Is it safe to go to sea tomorrow morning from Chennai?'",
               "मैं इनमें मदद कर सकता हूँ: संभावित मछली पकड़ने के क्षेत्र, समुद्री सुरक्षा, ज्वार/मौसम/समुद्र की स्थिति, चक्रवात/बिजली चेतावनी, "
               "क्लोरोफिल और SST, और सीमा (जियोफेंस) जाँच। उदाहरण: 'क्या कल सुबह चेन्नई से समुद्र में जाना सुरक्षित है?'",
               "நான் உதவ முடியும்: மீன்பிடி மண்டலங்கள், கடல் பாதுகாப்பு, ஓதம்/வானிலை/கடல் நிலை, புயல்/மின்னல் எச்சரிக்கை, "
               "குளோரோபில் & SST, எல்லை (ஜியோஃபென்ஸ்) சோதனை. எடுத்துக்காட்டு: 'நாளை காலை சென்னையிலிருந்து கடலுக்குச் செல்வது பாதுகாப்பா?'",
               "నేను సహాయం చేయగలను: చేపల వేట ప్రాంతాలు, సముద్ర భద్రత, ఆటుపోట్లు/వాతావరణం/సముద్ర పరిస్థితులు, తుఫాను/పిడుగు హెచ్చరికలు, "
               "క్లోరోఫిల్ & SST, సరిహద్దు (జియోఫెన్స్) తనిఖీ. ఉదాహరణ: 'రేపు ఉదయం చెన్నై నుండి సముద్రంలోకి వెళ్లడం సురక్షితమా?'"),
    "deferred": _t("Route optimisation and 'why did productivity decline' analysis are planned for the next phase.",
                   "मार्ग अनुकूलन और 'उत्पादकता क्यों घटी' विश्लेषण अगले चरण में आएँगे।",
                   "வழித்தட மேம்பாடு மற்றும் 'உற்பத்தி ஏன் குறைந்தது' பகுப்பாய்வு அடுத்த கட்டத்தில் வரும்.",
                   "మార్గ ఆప్టిమైజేషన్, 'ఉత్పాదకత ఎందుకు తగ్గింది' విశ్లేషణ తదుపరి దశలో వస్తాయి."),
    "lang_fallback": _t("({lang} detected. Full replies are available in English, Hindi, Tamil and Telugu for now.)",
                        "", "", ""),
}


def t(key: str, lang: str, **kw) -> str:
    entry = TR[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**kw) if kw else text
