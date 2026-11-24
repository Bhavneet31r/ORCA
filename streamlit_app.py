"""Streamlit interface for the ORCA ocean and coastal assistant."""
from __future__ import annotations

import re
from typing import Any

import streamlit as st

from config import APP_NAME, LOCATIONS
from main import _build_result
from models import AnalysisResult
from prompt_engineering import (
    MODEL_NAME,
    PROMPT_VERSIONS,
    TEST_INPUTS,
    build_prompt,
    call_gemini,
    gemini_is_configured,
    get_gemini_model,
)


FEATURE_PROMPTS = [
    ("01 · Ocean science", "What causes ocean tides?"),
    ("02 · Sea conditions", "What are the sea conditions tomorrow morning?"),
    ("03 · Fishing-zone estimate", "Find a potential fishing zone"),
    ("04 · Boundary distances", "Check nearby coastal boundaries"),
    ("05 · Forecast signals", "Are there marine weather alerts?"),
]
WELCOME_PROMPTS = [
    ("How do tides work?", "What causes ocean tides?"),
    ("Why are reefs bleaching?", "Why are coral reefs bleaching?"),
    ("Check tomorrow's conditions", "Is it safe to go fishing tomorrow morning?"),
]


st.set_page_config(
    page_title=f"{APP_NAME} | Ocean & Coastal Assistant",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.session_state.setdefault("conversation", [])
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(165deg, #062530, #0b3541 66%, #082a36);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #e9f4f2;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #a7c3c4;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        color: #e7f2ef;
        background: rgba(255, 255, 255, .045);
        border-color: rgba(201, 231, 227, .15);
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
        color: #fff;
        background: rgba(255, 255, 255, .10);
        border-color: rgba(140, 218, 204, .35);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _looks_like_location_only(text: str) -> bool:
    normalized = text.strip().casefold()
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*[,;]\s*[+-]?\d+(?:\.\d+)?", normalized):
        return True
    return any(
        normalized == alias.casefold()
        for location in LOCATIONS.values()
        for alias in location["aliases"]
    )


def _submit_query(query: str, selected_location: str | None) -> None:
    text = query.strip()
    if not text:
        return

    pending_query = st.session_state.get("pending_query")
    if pending_query and _looks_like_location_only(text):
        text = f"{pending_query} {text}"
    st.session_state["pending_query"] = None

    st.session_state["conversation"].append(
        {"role": "user", "content": query.strip()}
    )
    result = _build_result(text, selected_location)
    st.session_state["conversation"].append(
        {
            "role": "assistant",
            "content": result.answer or result.summary,
            "result": result,
        }
    )
    if result.mode == "need_location":
        st.session_state["pending_query"] = text


def _render_advisory_details(result: AnalysisResult) -> None:
    weather = result.weather
    if weather:
        st.markdown("#### Sea and weather")
        columns = st.columns(3)
        columns[0].metric("Condition level", weather.get("status", "UNKNOWN"))
        wave = weather.get("wave")
        columns[1].metric(
            "Maximum wave",
            f"{wave} m" if wave is not None else "Unavailable",
        )
        gust = weather.get("gust")
        columns[2].metric(
            "Peak gust",
            f"{gust} km/h" if gust is not None else "Unavailable",
        )
        st.caption(
            f"Forecast window: {weather.get('time_range', 'not available')} · "
            f"Source: {weather.get('source', 'not reported')}"
        )
        if weather.get("alerts"):
            st.warning("Forecast signals: " + "; ".join(weather["alerts"]))
        elif not weather.get("available"):
            st.caption("Live weather data is unavailable; no synthetic forecast is shown.")

    pfz = result.pfz
    if pfz:
        st.markdown("#### Potential fishing-zone estimate")
        if pfz.get("available"):
            columns = st.columns(3)
            columns[0].metric(
                "Candidate distance",
                f"{pfz['distance_km']} km {pfz['direction']}",
            )
            columns[1].metric("Chlorophyll", f"{pfz['chl']} mg/m³")
            columns[2].metric("Sea-surface temperature", f"{pfz['sst']} °C")
            st.caption(
                f"Coordinates: {pfz['latitude']}, {pfz['longitude']} · "
                f"Observation: {pfz.get('observation_date', 'date unavailable')} · "
                f"Estimated travel time: {pfz.get('estimated_hours_at_8_knots', 'n/a')} h "
                "at 8 knots."
            )
            st.caption(
                "Satellite indicators are not official fishing or safety advice."
            )
        else:
            st.info(pfz.get("message", "Current satellite data is unavailable."))
        if pfz.get("source"):
            st.caption(f"Satellite source: {pfz['source']}")

    boundaries = result.geofence.get("items", [])
    if boundaries:
        st.markdown("#### Nearby boundaries and protected areas")
        st.dataframe(
            [
                {
                    "Area": item["name"],
                    "Type": item["kind"],
                    "Distance (km)": item["distance_km"],
                    "Inside": item["inside"],
                    "Near": item["near"],
                }
                for item in sorted(boundaries, key=lambda item: item["distance_km"])
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(result.geofence.get("message", "Approximate distances only."))


def _render_assistant_message(message: dict[str, Any]) -> None:
    result = message.get("result")
    answer = message["content"]
    if result is None:
        st.markdown(answer)
        return

    if result.status == "warning":
        st.warning(answer)
    else:
        st.success(answer)

    if result.mode == "advisory":
        with st.expander("Analysis details"):
            _render_advisory_details(result)
    elif result.mode == "need_location":
        st.caption(
            "Choose a coastal location in the sidebar, or reply with a supported "
            "location name or coordinates."
        )


st.title("Ask ORCA")
st.caption(
    "Educational prototype only. Not an official marine safety, navigation, "
    "weather-warning, or fishing service."
)

with st.sidebar:
    st.markdown("## ORCA")
    st.caption("Ocean & coastal assistant")
    location_options = [""] + sorted(
        LOCATIONS,
        key=lambda key: LOCATIONS[key]["name"],
    )
    selected_location = st.selectbox(
        "Coastal location",
        options=location_options,
        format_func=lambda key: (
            "Auto-detect from question" if not key else LOCATIONS[key]["name"]
        ),
        key="analysis_location",
    )
    st.caption("You can also include coordinates, for example `13.08, 80.35`.")
    st.markdown("### Try a feature")
    quick_query = None
    for label, feature_query in FEATURE_PROMPTS:
        if st.button(label, key=f"feature_{label[:2]}", width="stretch"):
            quick_query = feature_query
    st.warning(
        "Prototype only. Forecasts and boundary areas are approximate; always "
        "follow official marine advisories."
    )

assistant_tab, prompt_tab = st.tabs(["Ask ORCA", "Prompt Lab"])

with assistant_tab:
    st.subheader("Explore the ocean or check a coastal location")
    st.write(
        "Ask a general ocean-science question, or select a location to explore "
        "conditions, fishing-zone estimates, alerts, and nearby boundaries."
    )

    if not st.session_state.get("conversation"):
        columns = st.columns(len(WELCOME_PROMPTS))
        for column, (label, welcome_query) in zip(columns, WELCOME_PROMPTS):
            if column.button(label, key=f"welcome_{label}", width="stretch"):
                quick_query = welcome_query

    submitted_query = st.chat_input(
        "Ask about tides, marine life, sea conditions, satellite estimates, or boundaries"
    )
    query_to_submit = submitted_query or quick_query
    if query_to_submit:
        with st.spinner("ORCA is checking the information..."):
            _submit_query(query_to_submit, selected_location or None)

    for message in st.session_state.get("conversation", []):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                _render_assistant_message(message)
            else:
                st.markdown(message["content"])

    st.caption(
        "Forecast data is not an official warning. Do not use prototype outputs "
        "for real-world navigation or fishing decisions."
    )

with prompt_tab:
    st.subheader("Compare zero-shot and few-shot prompts")
    model_name = get_gemini_model()
    key_status = "configured" if gemini_is_configured() else "not configured"
    st.caption(f"Model: {model_name or MODEL_NAME} · Gemini API key: {key_status}")

    with st.form("prompt_form"):
        strategy = st.radio(
            "Prompt strategy",
            options=["zero-shot", "few-shot"],
            horizontal=True,
            key="prompt_strategy",
        )
        prompt_input = st.text_area(
            "Test input",
            value=TEST_INPUTS[0]["input"],
            key="prompt_input",
            height=100,
        )
        context = st.text_area(
            "Optional retrieved context",
            key="prompt_context",
            height=100,
        )
        run_prompt = st.form_submit_button("Run prompt")

    if run_prompt:
        if not prompt_input.strip():
            st.session_state.pop("prompt_result", None)
            st.error("Enter a prompt test input.")
        else:
            messages = build_prompt(prompt_input, strategy, context)
            with st.spinner("Running Gemini prompt..."):
                response = call_gemini(messages["system"], messages["user"])
            st.session_state["prompt_result"] = {
                "messages": messages,
                "result": response,
            }

    prompt_output = st.session_state.get("prompt_result")
    if prompt_output is not None:
        response = prompt_output["result"]
        if response.get("available"):
            st.success(response["answer"])
        else:
            st.warning(response["answer"])

        with st.expander("Built prompt"):
            st.markdown("**System prompt**")
            st.code(prompt_output["messages"]["system"])
            st.markdown("**User prompt**")
            st.code(prompt_output["messages"]["user"])

    with st.expander("Prompt iterations and test inputs"):
        st.markdown("**Prompt iteration log**")
        st.dataframe(PROMPT_VERSIONS, hide_index=True, width="stretch")
        st.markdown("**Example test inputs**")
        st.dataframe(TEST_INPUTS, hide_index=True, width="stretch")
