# PTE Feature Architecture Docs (New)

Last verified: February 23, 2026

This folder documents each feature with four goals:
1. Short feature intent.
2. Real PTE behavior from public sources.
3. Current implementation in this codebase.
4. Simple architecture and remaining improvements.

## Shared Baselines
- `docs/new/architecture/shared/system_baseline.md`
- `docs/new/architecture/shared/speech_pipeline_baseline.md`
- `docs/new/architecture/shared/objective_task_baseline.md`
- `docs/new/architecture/shared/tts_audio_baseline.md`

## Speaking
- `docs/new/architecture/speaking/read_aloud.md`
- `docs/new/architecture/speaking/repeat_sentence.md`
- `docs/new/architecture/speaking/describe_image.md`
- `docs/new/architecture/speaking/retell_lecture.md`
- `docs/new/architecture/speaking/summarize_group_discussion.md`
- `docs/new/architecture/speaking/respond_to_a_situation.md`

## Listening
- `docs/new/architecture/listening/summarize_spoken_text.md`
- `docs/new/architecture/listening/multiple_choice_multiple.md`
- `docs/new/architecture/listening/multiple_choice_single.md`
- `docs/new/architecture/listening/fill_in_the_blanks.md`
- `docs/new/architecture/listening/select_missing_word.md`

## Reading
- `docs/new/architecture/reading/multiple_choice_multiple.md`
- `docs/new/architecture/reading/multiple_choice_single.md`
- `docs/new/architecture/reading/fill_in_the_blanks_dropdown.md`

## Writing
- `docs/new/architecture/writing/summarize_written_text.md`
- `docs/new/architecture/writing/write_essay.md`
- `docs/new/architecture/writing/write_email.md`

## Core Source Links
- PTE Academic Speaking/Writing format: https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
- PTE Academic Reading format: https://www.pearsonpte.com/pte-academic/test-format/reading
- PTE Academic Listening format: https://www.pearsonpte.com/pte-academic/test-format/listening
- PTE Core Speaking/Writing format: https://www.pearsonpte.com/pte-core/test-format/speaking-writing
- PTE Academic Score Guide PDF: https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf

Note: Pearson does not publish full production scoring algorithms. Where rules are not fully public, these docs clearly mark our implementation as heuristic/practice-oriented.
