import sys
sys.path.insert(1, str('../sbbtracker'))

from sbbtracker.windows import main_windows


def test_url():
    assert("dev" not in main_windows.api_url)
