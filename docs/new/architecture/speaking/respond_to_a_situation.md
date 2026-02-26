# Respond to a Situation

## Feature (Short)
User reads/listens to a scenario and gives an extended spoken response.

## Real PTE (Public)
- Public format (PTE Academic / PTE Core speaking-writing pages) includes this task.
- Typical prompt: text up to 60 words; response time 40 seconds.

## Our Implementation
- Current status: UI placeholder only.
- Page: `api/templates/respond_to_a_situation.html`
- Route: `/speaking/respond-to-a-situation`
- No scoring pipeline implemented yet.

## Simple Architecture (Planned)
Scenario prompt -> user speech capture -> shared speech pipeline + scenario rubric evaluator (tone, purpose, structure)

## Reliability
- Not scorable yet; currently informational UI only.

## Remaining Improvements
- Add scenario dataset with communicative intents.
- Implement dedicated scoring for relevance, tone, and actionability.
- Reuse shared speech pipeline from Read Aloud once APIs are created.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
- https://www.pearsonpte.com/pte-core/test-format/speaking-writing
