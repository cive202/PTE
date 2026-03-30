import sys
import types
import math
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


def _install_jiwer_stub_if_needed():
    try:
        import jiwer  # noqa: F401
        return
    except Exception:
        pass

    def _wer(reference: str, hypothesis: str) -> float:
        ref_tokens = reference.split()
        hyp_tokens = hypothesis.split()
        if not ref_tokens:
            return 0.0 if not hyp_tokens else 1.0

        rows = len(ref_tokens) + 1
        cols = len(hyp_tokens) + 1
        dp = [[0] * cols for _ in range(rows)]
        for i in range(rows):
            dp[i][0] = i
        for j in range(cols):
            dp[0][j] = j

        for i in range(1, rows):
            for j in range(1, cols):
                cost = 0 if ref_tokens[i - 1] == hyp_tokens[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + cost,
                )

        return dp[-1][-1] / len(ref_tokens)

    stub = types.ModuleType("jiwer")
    stub.wer = _wer
    sys.modules["jiwer"] = stub


_install_jiwer_stub_if_needed()


def _install_cmudict_stub_if_needed():
    try:
        import cmudict  # noqa: F401
        return
    except Exception:
        pass

    stub = types.ModuleType("cmudict")
    stub.dict = lambda: {}
    sys.modules["cmudict"] = stub


def _install_g2p_en_stub_if_needed():
    try:
        import g2p_en  # noqa: F401
        return
    except Exception:
        pass

    class _G2p:
        def __call__(self, _word):
            return []

    stub = types.ModuleType("g2p_en")
    stub.G2p = _G2p
    sys.modules["g2p_en"] = stub


_install_cmudict_stub_if_needed()
_install_g2p_en_stub_if_needed()


def _install_numpy_stub_if_needed():
    try:
        import numpy  # noqa: F401
        return
    except Exception:
        pass

    class _Array(list):
        def __pow__(self, power):
            return _Array([value ** power for value in self])

    def _mean(values):
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    stub = types.ModuleType("numpy")
    stub.sqrt = math.sqrt
    stub.mean = _mean
    stub.ndarray = _Array
    sys.modules["numpy"] = stub


def _install_librosa_stub_if_needed():
    try:
        import librosa  # noqa: F401
        return
    except Exception:
        pass

    def _load(_audio_path, sr=16000, offset=0, duration=None):
        return [], sr

    stub = types.ModuleType("librosa")
    stub.load = _load
    sys.modules["librosa"] = stub


_install_numpy_stub_if_needed()
_install_librosa_stub_if_needed()


@pytest.fixture
def client():
    from api.app import app as flask_app

    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client
