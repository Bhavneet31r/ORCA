from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_answers_general_ocean_question():
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.text_area(key="analysis_query").set_value("What causes ocean tides?")
    app.button[0].click().run()

    assert not app.exception
    assert any("Moon" in element.value for element in app.success)
