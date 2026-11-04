from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_dashboard_runs_with_the_review_snapshot():
    app_path = Path(__file__).resolve().parents[1] / "streamlit" / "app.py"
    dashboard = AppTest.from_file(str(app_path), default_timeout=60).run()

    assert not dashboard.exception
    assert len(dashboard.metric) == 5
    assert len(dashboard.tabs) == 4
