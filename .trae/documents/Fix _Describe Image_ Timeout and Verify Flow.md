**Analysis of the "Describe Image" Failure**
The "Describe Image" feature was failing because the Whisper `turbo` model, while highly accurate, takes a significant amount of time to process audio when running on a CPU. The previous timeout was set to 120 seconds, which was being exceeded, causing the Flask application to report a failure even while the ASR service was still working in the background.

**Changes Implemented**
1. **Increased HTTP Timeouts**:
   - Updated [app.py](file:///c:/Users/Acer/DataScience/PTE/api/app.py) to increase the transcription request timeout from 120s to **300s** (5 minutes) for both Image and Lecture evaluation jobs.
   - Updated [validator.py](file:///c:/Users/Acer/DataScience/PTE/api/validator.py) to increase the ASR service timeout and the Docker MFA alignment timeout to **300s**.
2. **Verified Data Paths**: Confirmed that [image_references.json](file:///c:/Users/Acer/DataScience/PTE/data/image_references.json) and the corresponding images in [data/images/](file:///c:/Users/Acer/DataScience/PTE/data/images) are correctly located and accessible.
3. **Confirmed ASR Health**: Verified that the ASR service is correctly loading the `turbo` model and is capable of processing requests, albeit slowly on CPU.

**Verification Results**
- The ASR service is confirmed healthy and listening on port 8000.
- The Flask application has reloaded with the new 300s timeout settings.
- The `turbo` model is confirmed to be running in `fp32` mode for maximum stability.

**Next Steps**
Please try using the "Describe Image" task again. Since the `turbo` model is quite heavy on the CPU, it may take 2-3 minutes to return a result, but the system will now wait long enough to receive it without timing out.