import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_panphon_stub_if_needed():
    try:
        import panphon  # noqa: F401
        return
    except Exception:
        pass

    class _Segment:
        def __init__(self, symbol):
            self.symbol = symbol

        def hamming_distance(self, other):
            return 0 if self.symbol == other.symbol else 9

    class _FeatureTable:
        def fts(self, ipa_symbol):
            if not ipa_symbol:
                return []
            return [_Segment(ipa_symbol)]

    stub = types.ModuleType("panphon")
    stub.FeatureTable = _FeatureTable
    sys.modules["panphon"] = stub


_install_panphon_stub_if_needed()


@pytest.fixture
def client():
    from api.app import app as flask_app

    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client
