from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_answers_general_ocean_question():
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)

    app.chat_input[0].set_value("What causes ocean tides?").run(timeout=10)

    assert not app.exception
    assert any("Moon" in element.value for element in app.success)


def test_streamlit_app_keeps_all_feature_shortcuts():
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)
    labels = {button.label for button in app.button}

    assert {
        "01 · Ocean science",
        "02 · Sea conditions",
        "03 · Fishing-zone estimate",
        "04 · Boundary distances",
        "05 · Forecast signals",
    }.issubset(labels)
