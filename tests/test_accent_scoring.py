import unittest
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pte_core.scoring.accent_scorer import PhonemeNormalizer, AccentTolerantScorer

class TestAccentScoring(unittest.TestCase):
    def setUp(self):
        self.normalizer = PhonemeNormalizer()
        self.scorer = AccentTolerantScorer()

    def test_normalization(self):
        # Test basic mapping
        self.assertEqual(self.normalizer.normalize('AH0'), 'ə')
        self.assertEqual(self.normalizer.normalize('EH1'), 'ɛ')
        self.assertEqual(self.normalizer.normalize('K'), 'k')
        self.assertEqual(self.normalizer.normalize('T'), 't')
        
    def test_exact_match(self):
        score = self.scorer.score_word(
            ['k', 'ae', 't'], 
            ['k', 'ae', 't']
        )
        self.assertGreaterEqual(score['accuracy'], 95)

    def test_accent_indian_substitution(self):
        # Test Indian 't' for 'th'
        # θ -> t̪ (dental t)
        # θ -> t̪ (dental t)
        score_th, is_sub = self.scorer.score_phoneme_pair('θ', 't̪', 'Indian English')
        # Expect 0.70 based on new configuration
        self.assertAlmostEqual(score_th, 0.70, places=2)
        self.assertTrue(is_sub, "Should be flagged as substitution")
        
        # Whole word "think" -> "tink"
        # Expected: θ ɪ ŋ k
        # Spoken: t̪ ɪ ŋ k
        # Note: input to score_word should be list of IPA or ARPA? 
        # The scorer's score_word takes raw input and normalizes internally? 
        # Wait, score_word implementation calls score_phoneme_pair which normalizes.
        # But score_word calls align_sequences which also normalizes.
        # So we can pass IPA or ARPA as long as they normalize correctly.
        # Let's pass IPA to be safe as our new scorer seems to expect that or ARPA.
        
        expected = ['θ', 'ɪ', 'ŋ', 'k']
        spoken = ['t̪', 'ɪ', 'ŋ', 'k']
        
        res = self.scorer.score_word(expected, spoken, 'Indian English')
        print(f"Indian 'think'->'tink' score: {res['accuracy']}")
        # Previous score was ~99%. New expectation: 70-80% due to non-perfect substitution score
        self.assertTrue(70 <= res['accuracy'] <= 85, f"Score {res['accuracy']} not in 70-85 range")

    def test_welfare_example(self):
        # Example 1: "welfare"
        # Expected (MFA/ARPAbet converted to IPA): w ɛ l f ɛ r
        # Spoken (Wav2Vec/IPA): ʋ ɛ l k ɛ:
        
        expected = ['w', 'ɛ', 'l', 'f', 'ɛ', 'r']
        spoken = ['ʋ', 'ɛ', 'l', 'k', 'ɛ'] # missing r, k instead of f, v instead of w
        
        res = self.scorer.score_word(expected, spoken, 'Non-Native English')
        print(f"Welfare score: {res['accuracy']}")
        # Target: 40-60% (Major errors: k instead of f, missing r)
        self.assertTrue(40 <= res['accuracy'] <= 60, f"Score {res['accuracy']} not in 40-60 range")

    def test_economic_example(self):
        # Example 2: "economic"
        # Expected: ɛ k ə n ɑ m ɪ k
        # Spoken: ɛ k ɔ n ɔ mʲ i k
        
        expected = ['ɛ', 'k', 'ə', 'n', 'ɑ', 'm', 'ɪ', 'k']
        spoken =   ['ɛ', 'k', 'ɔ', 'n', 'ɔ', 'm', 'i', 'k'] # simplified vowels
        
        res = self.scorer.score_word(expected, spoken, 'Non-Native English')
        print(f"Economic score: {res['accuracy']}")
        # Target: 55-75% (Intelligible but many vowel shifts)
        self.assertTrue(55 <= res['accuracy'] <= 75, f"Score {res['accuracy']} not in 55-75 range")

    def test_bad_pronunciation(self):
        # completely wrong
        expected = ['k', 'ae', 't']
        spoken = ['d', 'o', 'g']
        
        res = self.scorer.score_word(expected, spoken, 'Non-Native English')
        print(f"Cat->Dog score: {res['accuracy']}")
        self.assertLessEqual(res['accuracy'], 30)

if __name__ == '__main__':
    unittest.main()
