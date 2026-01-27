I will implement strict **Stress Matching** and generate a report highlighting stress errors.

### **Implementation Details**
1.  **Modify `test_mfa_output.py`**:
    *   **Logic**: I will split validation into two layers:
        *   **Layer 1 (Phonemes)**: Do the sounds match? (e.g., `AH` == `AH`).
        *   **Layer 2 (Stress)**: If Layer 1 passes, do the stress markers match? (e.g., `AH1` vs `AH0`).
    *   **Stress Mismatch Detection**: A word is flagged as a "Stress Error" if the phonemes are correct but the stress pattern (0/1/2) is wrong.
    *   **Reporting**: I will add a `stress_errors` list to the JSON report.

2.  **Run Validation**:
    *   Execute the updated script on the existing TextGrids.

3.  **Deliver Result**:
    *   I will read the report and explicitly list the words where **Stress Mismatches** were detected.

I will start by updating the script immediately.
