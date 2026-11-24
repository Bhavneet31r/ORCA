"""Streamlit interface for the ORCA ocean and coastal assistant."""
from __future__ import annotations

import os

import streamlit as st

from config import APP_NAME, DEFAULT_QUERY, LOCATIONS
from main import _build_result
from prompt_engineering import (
    MODEL_NAME,
    PROMPT_VERSIONS,
    TEST_INPUTS,
    build_prompt,
    call_gemini,
)


st.set_page_config(page_title=f"{APP_NAME} | Ocean & Coastal Assistant", layout="wide")
st.title(f"{APP_NAME} | Ocean & Coastal Assistant")
st.caption(
    "Educational prototype only. It is not an official marine safety, navigation, "
    "weather-warning, or fishing service."
)

assistant_tab, prompt_tab = st.tabs(["Ocean Assistant", "Prompt Lab"])

with assistant_tab:
    with st.form("analysis_form"):
        query = st.text_area(
            "Ask about ocean science or coastal conditions",
            value=DEFAULT_QUERY,
            key="analysis_query",
            height=100,
        )
        location_options = [""] + sorted(
            LOCATIONS,
            key=lambda key: LOCATIONS[key]["name"],
        )
        selected_location = st.selectbox(
            "Preferred coastal location",
            options=location_options,
            format_func=lambda key: (
                "Auto-detect from question" if not key else LOCATIONS[key]["name"]
            ),
            key="analysis_location",
        )
        analyze = st.form_submit_button("Analyze")

    if analyze:
        st.session_state["analysis_result"] = _build_result(
            query.strip(),
            selected_location or None,
        )

    result = st.session_state.get("analysis_result")
    if result is not None:
        st.subheader(result.summary or "ORCA response")
        answer = result.answer or result.summary
        if result.status == "warning":
            st.warning(answer)
        else:
            st.success(answer)

        if result.mode == "advisory":
            if result.weather.get("available"):
                st.caption(
                    "Weather information is forecast data, not an official marine warning."
                )
            else:
                st.caption(
                    "Live weather data is unavailable; no synthetic forecast values are shown."
                )

        with st.expander("Analysis details"):
            st.write(f"Mode: {result.mode} | Language: {result.language}")
            if result.timestamp:
                st.write(f"Analyzed: {result.timestamp}")
            st.json(
                {
                    "weather": result.weather,
                    "satellite_estimate": result.pfz,
                    "illustrative_boundaries": result.geofence,
                }
            )

with prompt_tab:
    st.subheader("Compare prompt strategies")
    configured = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    key_status = "configured" if configured else "not configured"
    st.caption(f"Model: {MODEL_NAME} | Gemini API key: {key_status}")

    with st.form("prompt_form"):
        strategy = st.radio(
            "Prompt strategy",
            options=["zero-shot", "few-shot"],
            horizontal=True,
        )
        prompt_input = st.text_area(
            "Test input",
            value=TEST_INPUTS[0]["input"],
            key="prompt_input",
            height=100,
        )
        context = st.text_area(
            "Optional context",
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
            st.session_state["prompt_result"] = {
                "messages": messages,
                "result": call_gemini(messages["system"], messages["user"]),
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
        st.table(PROMPT_VERSIONS)
        st.table(TEST_INPUTS)
