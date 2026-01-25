
import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(r"c:\Users\Acer\DataScience\PTE")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pte_core.mfa.textgrid_reader import read_word_textgrid
from pte_core.mfa.phone_reader import read_phone_textgrid

def debug_uk_textgrid():
    textgrid_path = Path(r"c:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER\output_uk\Education.TextGrid")
    
    print(f"Reading: {textgrid_path}")
    words = read_word_textgrid(str(textgrid_path))
    phones = read_phone_textgrid(str(textgrid_path))
    
    # Find "education"
    target_word = None
    for w in words:
        if w["word"].lower() == "education":
            target_word = w
            break
            
    if not target_word:
        print("Word 'education' not found!")
        return
        
    print(f"\nWord 'education': {target_word}")
    w_start = target_word["start"]
    w_end = target_word["end"]
    
    print(f"Looking for phones between {w_start} and {w_end}...")
    
    # Print overlapping phones
    for p in phones:
        p_start = p["start"]
        p_end = p["end"]
        label = p["label"]
        
        # Check overlap
        if p_end > w_start and p_start < w_end:
            # Check strict containment (which is what test_mfa_output uses)
            is_contained = (p_start >= w_start - 0.001) and (p_end <= w_end + 0.001)
            
            print(f"Phone: {label:<5} [{p_start:.4f} - {p_end:.4f}] Contained? {is_contained}")

if __name__ == "__main__":
    debug_uk_textgrid()
