# Installing MFA for PTE Pipeline

## Current Status

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
