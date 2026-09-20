# Error extractor prompt

Analyze only the supplied learner evidence. Return JSON matching the provided schemas.

Inputs:

- transcript: {{transcript}}
- task: {{task}}
- learner_profile: {{learner_profile}}
- asr_metadata: {{asr_metadata}}
- existing_error_clusters: {{existing_error_clusters}}
- model_version: {{model_version}}
- skill_version: {{skill_version}}

Procedure:

1. Identify the learner's likely intended meaning.
2. Exclude acceptable variants and pure style preferences.
3. Select at most three high-value candidate errors.
4. Attach the exact evidence span and a narrow taxonomy label.
5. Lower confidence when ASR, intent, or context is uncertain.
6. Suggest a canonical key but do not merge records.
7. Produce a concise session summary and next-step recommendation.

Never invent audio details from text. Never infer a stable weakness from one event.
