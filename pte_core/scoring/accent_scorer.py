import panphon
import difflib
from typing import List, Dict, Tuple, Optional

# --- 1. ARPAbet ↔ IPA Normalization ---

class PhonemeNormalizer:
    """
    Converts between ARPAbet (MFA output) and IPA (Wav2Vec2/Panphon input).
    """
    
    # Mapping from ARPAbet to IPA
    # Based on standard mappings + common variations
    ARPABET_TO_IPA = {
        # Vowels (with auto-handling of stress markers 0,1,2)
        'AA': 'ɑ', 'AE': 'æ', 'AH': 'ʌ', 'AO': 'ɔ', 'EH': 'ɛ',
        'ER': 'ɜ', 'IH': 'ɪ', 'IY': 'i', 'UH': 'ʊ', 'UW': 'u',
        'AW': 'aʊ', 'AY': 'aɪ', 'EY': 'eɪ', 'OW': 'oʊ', 'OY': 'ɔɪ',
        # Consonants
        'B': 'b', 'D': 'd', 'G': 'g', 'K': 'k', 'P': 'p', 'T': 't',
        'DH': 'ð', 'F': 'f', 'HH': 'h', 'S': 's', 'SH': 'ʃ', 'TH': 'θ',
        'V': 'v', 'Z': 'z', 'ZH': 'ʒ', 'CH': 'tʃ', 'JH': 'dʒ',
        'M': 'm', 'N': 'n', 'NG': 'ŋ', 'L': 'l', 'R': 'r', 'W': 'w', 'Y': 'j'
    }

    # Special handling for reduced vowels/schwa
    SPECIAL_CASES = {
        'AH0': 'ə',
        'ER0': 'ɚ',
        'DX': 'ɾ'  # Flap T
    }

    def normalize(self, phoneme: str) -> str:
        """
        Convert ARPAbet phoneme (potentially with stress) to IPA.
        Example: 'AH0' -> 'ə', 'EH1' -> 'ɛ', 'K' -> 'k'
        """
        if not phoneme:
            return ""
            
        p = phoneme.upper()
        
        # Check special cases first
        if p in self.SPECIAL_CASES:
            return self.SPECIAL_CASES[p]
            
        # Strip stress digits for general mapping
        base = ''.join([c for c in p if not c.isdigit()])
        
        return self.ARPABET_TO_IPA.get(base, base.lower())

# --- 2. Accent-Specific Substitutions ---

ACCENT_SUBSTITUTIONS = {
    'Indian English': {
        'θ': ['t̪', 't', 'ʈ'],      # "think" → dental/retroflex t
        'ð': ['d̪', 'd', 'ɖ'],      # "this" → dental/retroflex d
        'æ': ['ɛ', 'e'],           # "cat" → more like "ket"
        'ɔ': ['o', 'ɔː'],          # Different vowel realization
        'v': ['w', 'ʋ'],           # v/w confusion
        'z': ['ʒ', 's'],           # z variations
        'ɹ': ['r', 'ɾ'],           # Different r sounds
        'w': ['v', 'ʋ'],           # w/v confusion
        'f': ['pʰ', 'ph'],         # f/ph confusion
    },
    
    'Nigerian English': {
        'θ': ['t'],                # "think" → "tink"
        'ð': ['d'],                # "this" → "dis"
        'ɹ': ['ɾ'],                # Tapped r
        'ɔ': ['o'],
        'ʌ': ['ɔ'],                # strut -> lot
        'ɪ': ['i'],                # kit -> fleece
    },
    
    'United Kingdom': {
        'ɑ': ['ɒ', 'ɔ'],           # Different "o" sounds
        'æ': ['a'],
        'ɹ': ['ɹ̠'],               # Different r articulation
        't': ['ʔ'],                # Glottal stop
    },
    
    'Non-Native English': {
        # Comprehensive list of common accepted substitutions for learners
        'θ': ['t̪', 't', 's', 'f'],
        'ð': ['d̪', 'd', 'z', 'v'],
        'æ': ['ɛ', 'e', 'a'],
        'ɹ': ['r', 'ɾ', 'l'],
        'v': ['w', 'ʋ', 'b'],
        'w': ['v', 'ʋ'],
        'ŋ': ['n', 'ŋg'],
        'ɪ': ['i'],                # tense/lax confusion
        'ʊ': ['u'],                # tense/lax confusion
        'ə': ['a', 'e', 'o', 'u'], # schwa realization
        'dʒ': ['z', 'ʒ'],          # joy -> zoy
        'tʃ': ['s', 'ʃ'],          # chair -> share
    }
}

# --- 3. Main Scoring Logic ---

class AccentTolerantScorer:
    # Configuration for scoring strictness
    CONFIG = {
        'accent_substitution_score': 0.70,  # Reduced from 0.90
        'tolerance_boost': 1.00,            # Removed (was 1.03-1.10)
        'length_penalty_per_phoneme': 8,    # % penalty per missing/extra phoneme
        'similarity_scores': {
            'exact': 1.00,
            'very_similar': 0.65,     # distance 1-2 (was 0.80)
            'moderately_similar': 0.50, # distance 3-4 (was 0.65)
            'somewhat_similar': 0.35,   # distance 5-6 (was 0.45)
            'quite_different': 0.20,    # distance 7-8 (was 0.25)
            'very_different': 0.05,     # distance 9+ (was 0.10)
        }
    }

    # New config for overall penalty
    NON_TARGET_PENALTY = 15.0 # Subtract 15% from final score if accent substitution used

    # Critical error pairs (should score lower)
    # Format: (expected_ipa, spoken_ipa): score
    CRITICAL_ERRORS = {
        ('f', 'k'): 0.15,  # Very different sounds
        ('θ', 'f'): 0.20,  # Common but wrong
        ('p', 't'): 0.20,  # Different place
        ('b', 'g'): 0.20,  # Different place
    }

    def __init__(self):
        # Downgraded to panphon 0.20.0 for compatibility
        self.ft = panphon.FeatureTable()
        self.normalizer = PhonemeNormalizer()

    def score_phoneme_pair(self, expected: str, spoken: str, accent: str = 'Non-Native English') -> Tuple[float, bool]:
        """
        Score a pair of phonemes based on:
        1. Exact match (1.0)
        2. Accent-acceptable substitution (0.70)
        3. Phonetic feature distance (0.05 - 0.65)
        4. Critical errors (0.15 - 0.20)
        
        Returns: (score, is_accent_substitution)
        """
        # Handle insertions/deletions placeholder
        # Handle insertions/deletions placeholder
        if expected == '-' or spoken == '-':
            return 0.0, False
            
        # Normalize to IPA
        exp_ipa = self.normalizer.normalize(expected)
        spk_ipa = self.normalizer.normalize(spoken)
        
        # Level 1: Exact match
        if exp_ipa == spk_ipa:
            return 1.0, False
            
        # Level 1.5: Critical Errors
        if (exp_ipa, spk_ipa) in self.CRITICAL_ERRORS:
            return self.CRITICAL_ERRORS[(exp_ipa, spk_ipa)], False

        # Level 2: Accent-acceptable substitution
        # Check if the spoken phoneme is in the allowed substitutions for the expected phoneme
        if spk_ipa in ACCENT_SUBSTITUTIONS.get(accent, {}).get(exp_ipa, []):
            return self.CONFIG['accent_substitution_score'], True  # 0.70, Is Substitution
            
        # Level 3: Phonetic Feature Distance
        try:
            # panphon.fts returns a list of Segments. We expect single segments.
            exp_segs = self.ft.fts(exp_ipa)
            spk_segs = self.ft.fts(spk_ipa)
            
            # panphon.fts returns a list of Segments. We expect single segments.
            exp_segs = self.ft.fts(exp_ipa)
            spk_segs = self.ft.fts(spk_ipa)
            
            if not exp_segs: return 0.0, False
            exp_seg = exp_segs[0]
            
            if not spk_segs: return 0.0, False
            spk_seg = spk_segs[0]
            
            # Additional check for None (some versions might return None)
            if exp_seg is None or spk_seg is None:
                return 0.0, False
            
            # Calculate Hamming distance based on articulatory features
            dist = exp_seg.hamming_distance(spk_seg)
            
            # Stricter scoring curve
            if dist <= 2:
                return self.CONFIG['similarity_scores']['very_similar'], False # 0.65
            elif dist <= 4:
                return self.CONFIG['similarity_scores']['moderately_similar'], False # 0.50
            elif dist <= 6:
                return self.CONFIG['similarity_scores']['somewhat_similar'], False # 0.35
            elif dist <= 8:
                return self.CONFIG['similarity_scores']['quite_different'], False # 0.20
            else:
                return self.CONFIG['similarity_scores']['very_different'], False # 0.05
                
        except (ValueError, KeyError, IndexError, AttributeError) as e:
            # Fallback if panphon doesn't recognize the IPA
            return 0.0, False

    def align_sequences(self, seq1: List[str], seq2: List[str]) -> Tuple[List[str], List[str]]:
        """
        Align two phoneme sequences using SequenceMatcher (simpler than Needleman-Wunsch but effective for this).
        We align based on the normalized IPA forms to be more robust.
        """
        # Convert to IPA for alignment purposes
        seq1_ipa = [self.normalizer.normalize(p) for p in seq1]
        seq2_ipa = [self.normalizer.normalize(p) for p in seq2]
        
        matcher = difflib.SequenceMatcher(None, seq1_ipa, seq2_ipa)
        
        aligned_seq1 = []
        aligned_seq2 = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for k in range(i2 - i1):
                    aligned_seq1.append(seq1[i1 + k])
                    aligned_seq2.append(seq2[j1 + k])
            elif tag == 'replace':
                # Align substitutions 1-to-1 as far as possible
                len1 = i2 - i1
                len2 = j2 - j1
                min_len = min(len1, len2)
                
                for k in range(min_len):
                    aligned_seq1.append(seq1[i1 + k])
                    aligned_seq2.append(seq2[j1 + k])
                
                # Handle leftovers
                if len1 > len2: # Deletions
                    for k in range(min_len, len1):
                        aligned_seq1.append(seq1[i1 + k])
                        aligned_seq2.append('-')
                elif len2 > len1: # Insertions
                    for k in range(min_len, len2):
                        aligned_seq1.append('-')
                        aligned_seq2.append(seq2[j1 + k])
                        
            elif tag == 'delete':
                for k in range(i1, i2):
                    aligned_seq1.append(seq1[k])
                    aligned_seq2.append('-')
            elif tag == 'insert':
                for k in range(j1, j2):
                    aligned_seq1.append('-')
                    aligned_seq2.append(seq2[k])
                    
        return aligned_seq1, aligned_seq2

    def score_word(self, expected_phonemes: List[str], spoken_phonemes: List[str], accent: str = 'Non-Native English') -> dict:
        """
        Score an entire word based on phoneme alignment and feature distance.
        """
        if not expected_phonemes:
            return {'accuracy': 0.0, 'phoneme_scores': [], 'alignment': []}
            
        # 1. Align sequences
        aligned_exp, aligned_spk = self.align_sequences(expected_phonemes, spoken_phonemes)
        
        # 2. Score aligned pairs
        phoneme_scores = []
        aligned_pairs = [] # Renamed from detailed_alignment
        used_accent_substitution = False
        
        for exp, spk in zip(aligned_exp, aligned_spk):
            score, is_sub = self.score_phoneme_pair(exp, spk, accent)
            if is_sub:
                used_accent_substitution = True
            
            phoneme_scores.append(score)
            aligned_pairs.append((exp, spk, score))
            
        # 3. Calculate Base Accuracy
        if not phoneme_scores:
            return {
                'accuracy': 0.0,
                'phoneme_scores': [],
                'alignment': aligned_pairs
            }
            
        base_accuracy = sum(phoneme_scores) / len(phoneme_scores) * 100
        
        # 4. Apply Length Penalty (NEW)
        # Deduct points if the number of spoken phonemes differs significantly
        expected_len = len([p for p in expected_phonemes if p])
        spoken_len = len([p for p in spoken_phonemes if p])
        length_diff = abs(expected_len - spoken_len)
        
        if length_diff > 0:
            penalty = length_diff * self.CONFIG['length_penalty_per_phoneme']
            base_accuracy = max(0, base_accuracy - penalty)

        # 5. Non-Target Penalty (NEW)
        # If accent substitutions were used, apply global penalty
        if used_accent_substitution:
            base_accuracy = max(0, base_accuracy - self.NON_TARGET_PENALTY)

        # 5. Global Accent Boosts (REMOVED/REDUCED)
        # We now rely on the specific substitution scores (0.70)
        # No extra boost is applied to keep scores realistic.
        
        return {
            'accuracy': round(base_accuracy, 1),
            'phoneme_scores': [round(s, 2) for s in phoneme_scores],
            'alignment': aligned_pairs
        }

    def score_word_variants(
        self,
        expected_variants: List[List[str]],
        spoken_phonemes: List[str],
        accent: str = 'Non-Native English',
    ) -> dict:
        """Score against multiple valid expected pronunciations and keep the best match."""
        if not expected_variants:
            return {
                'accuracy': 0.0,
                'phoneme_scores': [],
                'alignment': [],
                'expected_variant': [],
                'expected_variants_count': 0,
            }

        best_result = None
        for variant in expected_variants:
            candidate = self.score_word(variant, spoken_phonemes, accent)
            candidate['expected_variant'] = list(variant)
            candidate['expected_variants_count'] = len(expected_variants)
            if best_result is None or candidate.get('accuracy', 0.0) > best_result.get('accuracy', 0.0):
                best_result = candidate

        return best_result or {
            'accuracy': 0.0,
            'phoneme_scores': [],
            'alignment': [],
            'expected_variant': [],
            'expected_variants_count': len(expected_variants),
        }
