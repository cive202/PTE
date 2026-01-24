# Installing MFA for PTE Pipeline

## Current Status
import os
import shutil
import subprocess
from pathlib import Path
from google.colab import files as colab_files

# --- 1. Install MFA & Download Models ---
print("⏳ Installing Montreal Forced Aligner (this takes ~2-3 minutes)...")
# Install MFA and required dependencies
!mamba install -q -y -c conda-forge montreal-forced-aligner openblas

print("⬇️ Downloading English models...")
!mfa model download dictionary english_us_arpa
!mfa model download acoustic english_us_arpa

# --- 2. Setup Directories ---
base_dir = "/content"
input_dir = os.path.join(base_dir, "input_files")
corpus_dir = os.path.join(base_dir, "corpus")
output_dir = os.path.join(base_dir, "mfa_output")

# Clean and recreate directories
if os.path.exists(corpus_dir): shutil.rmtree(corpus_dir)
if os.path.exists(output_dir): shutil.rmtree(output_dir)
os.makedirs(input_dir, exist_ok=True)
os.makedirs(corpus_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# --- 3. Upload & Organize Files ---
print(f"\n📂 Created input folder at: {input_dir}")
print("👉 Please upload your .wav and .txt files into the 'input_files' folder on the left file panel now.")
input("⌨️  Press ENTER after you have finished uploading your files...")

print("🔄 Organizing corpus structure...")
files = os.listdir(input_dir)
wav_files = [f for f in files if f.endswith('.wav')]

if not wav_files:
    print("❌ No .wav files found! Please upload files to /content/input_files")
else:
    count = 0
    for wav_file in wav_files:
        audio_id = Path(wav_file).stem
        txt_file = f"{audio_id}.txt"
        
        if txt_file not in files:
            print(f"⚠️ Warning: Missing text file for {wav_file} (expected {txt_file})")
            continue
            
        # Create structure: corpus/audio_id/
        # This matches the structure expected by your project's aligner.py
        sample_dir = os.path.join(corpus_dir, audio_id)
        os.makedirs(sample_dir, exist_ok=True)
        
        shutil.copy2(os.path.join(input_dir, wav_file), os.path.join(sample_dir, wav_file))
        shutil.copy2(os.path.join(input_dir, txt_file), os.path.join(sample_dir, txt_file))
        count += 1

    if count > 0:
        # --- 4. Run Alignment ---
        print(f"🚀 Running MFA alignment on {count} samples...")
        # Flags match your project: --clean, --single_speaker, outputting JSON
        cmd = f"mfa align {corpus_dir} english_us_arpa english_us_arpa {output_dir} --clean --single_speaker --output_format json"
        
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if process.returncode == 0:
            print("✅ Alignment Complete!")
            
            # Zip results
            shutil.make_archive("/content/mfa_results", 'zip', output_dir)
            print("📦 Results zipped.")
            colab_files.download("/content/mfa_results.zip")
        else:
            print("❌ MFA Alignment Failed:")
            print(process.stdout)
            print(process.stderr)
    else:
        print("❌ No valid wav/txt pairs found to align.")import os
import shutil
import subprocess
from pathlib import Path
from google.colab import files as colab_files

# --- 1. Install MFA & Download Models ---
print("⏳ Installing Montreal Forced Aligner (this takes ~2-3 minutes)...")
# Install MFA and required dependencies
!mamba install -q -y -c conda-forge montreal-forced-aligner openblas

print("⬇️ Downloading English models...")
!mfa model download dictionary english_us_arpa
!mfa model download acoustic english_us_arpa

# --- 2. Setup Directories ---
base_dir = "/content"
input_dir = os.path.join(base_dir, "input_files")
corpus_dir = os.path.join(base_dir, "corpus")
output_dir = os.path.join(base_dir, "mfa_output")

# Clean and recreate directories
if os.path.exists(corpus_dir): shutil.rmtree(corpus_dir)
if os.path.exists(output_dir): shutil.rmtree(output_dir)
os.makedirs(input_dir, exist_ok=True)
os.makedirs(corpus_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# --- 3. Upload & Organize Files ---
print(f"\n📂 Created input folder at: {input_dir}")
print("👉 Please upload your .wav and .txt files into the 'input_files' folder on the left file panel now.")
input("⌨️  Press ENTER after you have finished uploading your files...")

print("🔄 Organizing corpus structure...")
files = os.listdir(input_dir)
wav_files = [f for f in files if f.endswith('.wav')]

if not wav_files:
    print("❌ No .wav files found! Please upload files to /content/input_files")
else:
    count = 0
    for wav_file in wav_files:
        audio_id = Path(wav_file).stem
        txt_file = f"{audio_id}.txt"
        
        if txt_file not in files:
            print(f"⚠️ Warning: Missing text file for {wav_file} (expected {txt_file})")
            continue
            
        # Create structure: corpus/audio_id/
        # This matches the structure expected by your project's aligner.py
        sample_dir = os.path.join(corpus_dir, audio_id)
        os.makedirs(sample_dir, exist_ok=True)
        
        shutil.copy2(os.path.join(input_dir, wav_file), os.path.join(sample_dir, wav_file))
        shutil.copy2(os.path.join(input_dir, txt_file), os.path.join(sample_dir, txt_file))
        count += 1

    if count > 0:
        # --- 4. Run Alignment ---
        print(f"🚀 Running MFA alignment on {count} samples...")
        # Flags match your project: --clean, --single_speaker, outputting JSON
        cmd = f"mfa align {corpus_dir} english_us_arpa english_us_arpa {output_dir} --clean --single_speaker --output_format json"
        
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if process.returncode == 0:
            print("✅ Alignment Complete!")
            
            # Zip results
            shutil.make_archive("/content/mfa_results", 'zip', output_dir)
            print("📦 Results zipped.")
            colab_files.download("/content/mfa_results.zip")
        else:
            print("❌ MFA Alignment Failed:")
            print(process.stdout)
            print(process.stderr)
    else:
        print("❌ No valid wav/txt pairs found to align.")
Based on your terminal output:
- ❌ **`env_aloud`**: MFA not installed
- ⚠️ **`aligner`**: MFA installed but broken (DLL error with `_kalpy`)

## Solution: Install MFA in `env_aloud`

### Step 1: Activate your main environment

```powershell
conda activate env_aloud
```

### Step 2: Install MFA

```powershell
conda install -c conda-forge montreal-forced-aligner
```

This will install MFA and all its dependencies (including `_kalpy` DLLs).

### Step 3: Verify Installation

```powershell
mfa --version
```

You should see something like:
```
Montreal Forced Aligner 3.x.x
```

### Step 4: Test Your Python Code

```powershell
cd "c:\Users\Acer\DataScience\PTE"
python test_mfa_setup.py
```

Should now show:
```
OK: MFA is installed and accessible
OK: MFA aligner module imports OK
```

---

## Alternative: If Conda Install Fails

If you get DLL errors or installation issues, try:

1. **Create a fresh conda environment**:
   ```powershell
   conda create -n env_aloud_mfa python=3.11
   conda activate env_aloud_mfa
   conda install -c conda-forge montreal-forced-aligner
   ```

2. **Or use pip** (less reliable, but sometimes works):
   ```powershell
   pip install montreal-forced-aligner
   ```

---

## Testing MFA with a Sample WAV

Once MFA is installed, you can test:

```python
import sys
sys.path.insert(0, "read_aloud")

from mfa.aligner import align_with_mfa

# Replace with your actual wav file path
wav_path = r"c:\Users\Acer\DataScience\PTE\sample.wav"
reference_text = "bicycle racing is the"  # Must match what's spoken

result = align_with_mfa(
    wav_path,
    reference_text,
    acoustic_model="english_us_arpa",
    dictionary="english_us_arpa",
    include_phones=True,
)

print("Words:", len(result.get("words", [])))
print("Phones:", len(result.get("phones", [])))
```

---

## Note About the `aligner` Environment

The `aligner` env has MFA but it's broken (DLL error). You can:
- **Ignore it** - use `env_aloud` instead
- **Or fix it** by reinstalling:
  ```powershell
  conda activate aligner
  conda remove montreal-forced-aligner
  conda install -c conda-forge montreal-forced-aligner
  ```

But for your PTE project, **stick with `env_aloud`** - that's where all your other dependencies are.
