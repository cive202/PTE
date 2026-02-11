# MFA Alignment Initialization Instructions

Run the following commands in PowerShell to generate TextGrid alignments for all 5 accents using the Montreal Forced Aligner (MFA) Docker image.

## Prerequisites
- Docker must be running.
- Ensure input files (`innovation_utsav.txt` and `innovation_utsav.wav`) are in `C:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER\data`.

## 1. Indian Accent
```powershell
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_indian_model/english_india_mfa.dict /data/eng_indian_model/english_mfa.zip /data/output_indian --clean
```

## 2. Nigerian Accent
```powershell
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_nigeria_model/english_nigeria_mfa.dict /data/eng_nigeria_model/english_mfa.zip /data/output_nigeria --clean
```

## 3. US Accent (ARPA Model)
```powershell
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_us_model/english_us_arpa.dict /data/eng_us_model/english_us_arpa.zip /data/output_us --clean
```

## 4. US Accent (MFA/IPA Model)
```powershell
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_us_model_2/english_us_mfa.dict /data/eng_us_model_2/english_mfa.zip /data/output_us_mfa --clean
```

## 5. UK Accent
```powershell
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/english_uk_model/english_uk_mfa.dict /data/english_uk_model/english_mfa.zip /data/output_uk --clean
```

## 6. Run Validation Report
After generating the TextGrids, run the Python script to validate the pronunciation:

```powershell
python c:\Users\Acer\DataScience\PTE\test_mfa_output.py
```
