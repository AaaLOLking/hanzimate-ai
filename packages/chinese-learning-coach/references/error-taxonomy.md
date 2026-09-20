# Learner Error Taxonomy

Use the narrowest supported type. Preserve uncertainty instead of forcing a label.

## pronunciation

- initial: 声母，如 z/zh、c/ch、s/sh、j/q/x；
- final: 韵母，如 an/ang、en/eng、ü/u；
- tone: 单字声调；
- tone-sandhi: 变调，如“不”“一”和三声变调；
- stress-rhythm: 轻重音、停顿和节奏；
- erhua-neutral-tone: 儿化或轻声；
- intelligibility: 综合可懂度。

Open conversation ASR is not sufficient for a precise pronunciation diagnosis. Require audio evidence or a pronunciation-assessment result.

## lexical

- word-choice；
- collocation；
- measure-word；
- register；
- false-friend；
- repetition-or-omission；
- word-formation。

## grammar

- word-order；
- aspect-le-guo-zhe；
- ba-construction；
- bei-construction；
- complement；
- comparison；
- classifier-structure；
- modifier-de-di-de；
- conjunction；
- question-form；
- negation；
- tense-time-expression；
- sentence-fragment。

## character-writing

- wrong-character；
- missing-character；
- homophone；
- stroke-or-component；
- punctuation；
- pinyin-orthography。

## listening

- sound-discrimination；
- word-boundary；
- key-detail；
- relation-or-reference；
- implied-meaning；
- speed-processing。

## pragmatics

- politeness；
- address-term；
- turn-taking；
- indirectness；
- context-appropriateness；
- cultural-assumption。

Do not label a valid regional, formal, informal, or learner-appropriate variant as wrong. Use a naturalness suggestion when meaning is clear and the form is acceptable.

## Severity

- blocking: meaning cannot be recovered or the task fails;
- major: meaning is recoverable but the error targets the lesson or recurs;
- minor: acceptable but noticeably unnatural;
- optional: style preference only.

## Confidence

- 0.90–1.00: direct and unambiguous evidence;
- 0.70–0.89: likely, but intent or transcription has minor uncertainty;
- 0.50–0.69: candidate only;
- below 0.50: do not create an error event.

## Canonical key

Build a stable deduplication key from type, subtype, target form, and relevant HSK tag. Never deduplicate only by vector similarity.
