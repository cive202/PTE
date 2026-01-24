
import nltk
from nltk.corpus import cmudict
import re
import os

def generate_arpa_dict():
    # Ensure cmudict is downloaded
    try:
        nltk.data.find('corpora/cmudict')
    except LookupError:
        nltk.download('cmudict')
    
    cmu = cmudict.dict()
    
    # Read the text file
    txt_path = r"c:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER\data\Education.txt"
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Tokenize (simple split and clean)
    words = set(re.findall(r"\b\w+\b", text.lower()))
    
    # Add some common words that might be missed or useful
    words.update(['sil', 'sp', 'spn'])
    
    output_path = r"c:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER\english_us_arpa.dict"
    
    found_count = 0
    missing_count = 0
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for word in sorted(words):
            if word in ['sil', 'sp', 'spn']:
                continue # specialized handling usually not needed in dict file for MFA if built-in
                
            if word in cmu:
                pronunciations = cmu[word]
                for pron in pronunciations:
                    # Join phones with space
                    pron_str = " ".join(pron)
                    f.write(f"{word}\t{pron_str}\n")
                found_count += 1
            else:
                print(f"Warning: Word '{word}' not found in CMUdict.")
                missing_count += 1
    
    print(f"Dictionary generated at: {output_path}")
    print(f"Words found: {found_count}")
    print(f"Words missing: {missing_count}")

if __name__ == "__main__":
    generate_arpa_dict()
