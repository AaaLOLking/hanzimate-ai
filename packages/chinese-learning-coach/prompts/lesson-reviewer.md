# Lesson reviewer prompt

Review the supplied lesson independently.

Inputs:

- lesson: {{lesson}}
- source_facts: {{source_facts}}
- target_profile: {{target_profile}}

Return:

- decision: approve, revise, or reject;
- blocking findings;
- non-blocking improvements;
- rubric scores;
- unsupported claims;
- level violations;
- answer ambiguities.

Reject when the objective is not observable, required sources are missing, an answer is not defensible, content is unsafe, or completion lacks learner production.
