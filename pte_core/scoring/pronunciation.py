from jiwer import wer
import difflib

def analyze_phoneme_errors(ref_phonemes, hyp_phonemes):
    """
    Align reference and hypothesis phonemes and return detailed errors.
    """
    matcher = difflib.SequenceMatcher(None, ref_phonemes, hyp_phonemes)
    analysis = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k, l in zip(range(i1, i2), range(j1, j2)):
                analysis.append({
                    "status": "match",
                    "ref": ref_phonemes[k],
                    "hyp": hyp_phonemes[l]
                })
        elif tag == 'replace':
            # Substitution
            # Try to align one-to-one as much as possible, then handle rest
            len_ref = i2 - i1
            len_hyp = j2 - j1
            min_len = min(len_ref, len_hyp)
            
            for k in range(min_len):
                analysis.append({
                    "status": "sub",
                    "ref": ref_phonemes[i1 + k],
                    "hyp": hyp_phonemes[j1 + k]
                })
            
            # Handle remaining
            if len_ref > len_hyp:
                # Extra refs = Deletions
                for k in range(i1 + min_len, i2):
                    analysis.append({
                        "status": "del",
                        "ref": ref_phonemes[k],
                        "hyp": None
                    })
            elif len_hyp > len_ref:
                # Extra hyps = Insertions
                for k in range(j1 + min_len, j2):
                    analysis.append({
                        "status": "ins",
                        "ref": None,
                        "hyp": hyp_phonemes[k]
                    })
                    
        elif tag == 'delete':
            for k in range(i1, i2):
                analysis.append({
                    "status": "del",
                    "ref": ref_phonemes[k],
                    "hyp": None
                })
        elif tag == 'insert':
            for l in range(j1, j2):
                analysis.append({
                    "status": "ins",
                    "ref": None,
                    "hyp": hyp_phonemes[l]
                })
                
    return analysis

def per(ref_phonemes, hyp_phonemes):
    ref_str = " ".join(ref_phonemes) if ref_phonemes else ""
    hyp_str = " ".join(hyp_phonemes) if hyp_phonemes else ""
    if not ref_str:
        return 1.0 if hyp_str else 0.0
    v = wer(ref_str, hyp_str)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v

def label_from_per(v):
    if v <= 0.15:
        return "correct"
    if v <= 0.35:
        return "acceptable"
    return "mispronounced"
