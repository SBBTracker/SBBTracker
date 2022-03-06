from sbbtracker.windows import main_windows


def test_url():
    assert("dev" not in main_windows.api_url)
