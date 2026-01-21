# PTE System Code Explanations

This folder contains detailed line-by-line explanations of all modules in the PTE (Pronunciation Test Engine) system.

## Files Overview

### 1. [word_level_matcher.md](01_word_level_matcher.md)
**Purpose**: Content accuracy detection through sequence alignment
- Tokenizes and normalizes reference text
- Aligns reference with ASR output using edit distance
- Detects missed, repeated, substituted, and correct words
- **Key**: Content errors come from sequence alignment only

### 2. [audio_quality.md](02_audio_quality.md)
**Purpose**: Audio clarity detection for routing pronunciation assessment
- Reads audio files (with fallback support)
- Computes silence ratio and RMS energy
- Decides if audio is clear based on ASR confidence + silence ratio
- **Key**: Audio clarity determines pronunciation method (MFA vs WavLM)

### 3. [mfa_pronunciation.md](03_mfa_pronunciation.md)
**Purpose**: Pronunciation assessment for clear audio using Montreal Forced Aligner
- Checks MFA installation
- Runs MFA alignment command-line tool
- Parses TextGrid output files
- Assesses pronunciation based on alignment quality
- **Key**: MFA provides precise phoneme-level alignment for clear audio

### 4. [wavlm_pronunciation.md](04_wavlm_pronunciation.md)
**Purpose**: Pronunciation assessment fallback for noisy audio using WavLM-CTC
- Loads WavLM neural network model
- Extracts phonemes from audio using CTC decoding
- Compares expected vs detected phonemes
- Assesses pronunciation with looser thresholds
- **Key**: WavLM-CTC is more robust to noise than MFA

### 5. [report_generator.md](05_report_generator.md)
**Purpose**: Unified report generation combining content and pronunciation results
- Merges content alignment with pronunciation assessment
- Applies decision rules (content errors take precedence)
- Combines timestamps from ASR and pronunciation sources
- Calculates statistics (accuracy, counts, average confidence)
- **Key**: Content errors override pronunciation assessment

### 6. [pte_pipeline.md](06_pte_pipeline.md)
**Purpose**: Main pipeline orchestrator coordinating all components
- Runs ASR transcription
- Performs content alignment
- Detects audio clarity
- Routes to MFA (clear) or WavLM (noisy)
- Generates unified report
- **Key**: Orchestrates entire pipeline with proper error handling

## System Architecture

```
Audio File + Reference Text
    ↓
[ASR] → Spoken words + timestamps
    ↓
[Word-Level Matching] → Content errors (missed/repeated/substituted)
    ↓
[Audio Clarity Detection] → Clear or Noisy?
    ↓
    ├─ Clear → [MFA] → Pronunciation assessment
    └─ Noisy → [WavLM] → Pronunciation assessment (fallback)
    ↓
[Report Generator] → Unified word-level report
    ↓
Final Report: {words, summary, metadata}
```

## Key Design Principles

1. **Separation of Concerns**
   - Content accuracy: Sequence alignment (word_level_matcher)
   - Pronunciation accuracy: Forced alignment (MFA/WavLM)
   - Never mix the two

2. **Audio Quality Routing**
   - Clear audio → MFA (precise, requires good quality)
   - Noisy audio → WavLM (robust, handles noise)

3. **Error Precedence**
   - Content errors (missed/repeated) override pronunciation
   - A word must be correctly spoken before pronunciation can be assessed

4. **Graceful Degradation**
   - MFA failure → Fallback to WavLM
   - Missing pronunciation → Default to correct
   - Invalid audio → Return safe defaults

## Usage

See each file's explanation for detailed line-by-line breakdowns. The explanations cover:
- Purpose of each line
- Why it's needed
- How it fits into the overall system
- Key algorithms and data structures

## Dependencies

- **ASR**: NeMo Parakeet-0.6B-v2 (voice2text.py)
- **MFA**: Montreal Forced Aligner (mfa_pronunciation.py)
- **WavLM**: microsoft/wavlm-base-plus (wavlm_pronunciation.py)
- **Audio Processing**: soundfile, scipy, numpy
- **Text Processing**: regex, textgrid (for MFA output)

## Notes

- All explanations assume Python 3.7+ with type hints
- Error handling is included but may need enhancement for production
- Some implementations are simplified (e.g., phoneme mapping, CTC decoding)
- Thresholds are configurable and may need tuning for specific use cases
