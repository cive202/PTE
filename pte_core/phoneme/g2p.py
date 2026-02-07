import re
from cmudict import dict as cmu_dict
from g2p_en import G2p

class PhonemeReferenceBuilder:
    def __init__(self):
        self.cmu = cmu_dict()
        self.g2p = G2p()
        self.cache = {}

    def get_stress_pattern(self, word: str):
        """Get stress pattern string (e.g. '010') for a word."""
        w = re.sub(r"[^a-zA-Z']+", "", word).lower()
        if not w:
            return None
            
        # Try CMU Dict first
        if w in self.cmu:
            # Use first pronunciation
            phones = self.cmu[w][0]
            # Extract numbers
            pattern = ""
            for p in phones:
                if p[-1].isdigit():
                    pattern += p[-1]
            return pattern
            
        # Fallback to G2P
        seq = self.g2p(w)
        pattern = ""
        for t in seq:
             # t is like "AH0"
             if t and t[-1].isdigit():
                 pattern += t[-1]
        
        return pattern if pattern else None

    def word_to_phonemes(self, word: str):
        w = re.sub(r"[^a-zA-Z']+", "", word).lower()
        if not w:
            return ["ah"]
        if w in self.cache:
            return self.cache[w]
        if w in self.cmu:
            phones = [p.lower() for p in self.cmu[w][0]]
        else:
            seq = self.g2p(w)
            phones = []
            for t in seq:
                if re.match(r"^[A-Z]{1,3}\d?$", t):
                    phones.append(t.lower())
            if not phones:
                phones = ["ah"]
        self.cache[w] = phones
        return phones

    def sentence_to_phonemes(self, text: str):
        tokens = re.findall(r"[A-Za-z']+|[.,;:!?]", text)
        result = []
        for t in tokens:
            if re.match(r"[.,;:!?]", t):
                result.append([t])
            else:
                result.append(self.word_to_phonemes(t))
        return result
