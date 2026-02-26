# Summarize Group Discussion

## Feature (Short)
Speaking task where user hears a multi-speaker discussion and delivers a spoken summary.

## Real PTE (Public)
- Public format lists this task with prompt up to 3 minutes and response time 2 minutes.
- It targets listening and speaking together.

## Our Implementation
- Current status: UI placeholder only.
- Page: `api/templates/summarize_group_discussion.html`
- Route: `/speaking/summarize-group-discussion`
- No production scoring endpoint yet.

## Simple Architecture (Planned)
Discussion audio -> speaking capture -> shared speech pipeline + discussion-content evaluator -> rubric feedback

## Reliability
- Not scorable yet; this feature is not production-ready.

## Remaining Improvements
- Implement task data model and `/speaking/summarize-group-discussion/*` APIs.
- Add multi-speaker transcript handling and speaker-turn weighting.
- Reuse retell-lecture scaffolding where possible, then specialize.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
