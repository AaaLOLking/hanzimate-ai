# Review Policy

Use FSRS scheduling in the host application. The Skill designs the activity and interprets evidence; it does not invent due dates when the scheduler is available.

## Review activity

1. Present a cue without the answer.
2. Require spoken or written retrieval.
3. Compare with an explicit answer rule.
4. Give a concise correction.
5. Ask for the learner's rating: Again, Hard, Good, or Easy.

## Vary the surface

Keep the target skill stable while changing:

- people, place, or object;
- numbers and time;
- communication goal;
- input modality;
- sentence polarity or question form.

Do not make a review harder by adding unrelated new grammar.

## Map errors to practice

- pronunciation: minimal contrast, listen-choose, repeat, delayed reproduction;
- lexical: cue-to-word, collocation choice, sentence completion, scenario use;
- grammar: transform, reorder, constrained production, role-play;
- character: sound-to-character, component distinction, short dictation;
- listening: key-detail extraction, paraphrase choice, short response;
- pragmatics: choose or produce the context-appropriate expression.

## Rating interpretation

- Again: failed recall or required the answer;
- Hard: correct only after substantial effort or partial hint;
- Good: correct without hint at reasonable effort;
- Easy: immediate correct retrieval plus successful transfer.

The application records the learner's rating. Model-estimated ratings are analytics only and must not silently replace it.

## Host application contract (v0.3)

- Only confirmed, active error memories create review cards. Rejected candidates and archived memories do not enter the queue.
- Serve only the cue and objective before submission. Reveal the reference answer and correction after a nonblank retrieval attempt; “不会” is a valid failed-recall response.
- Preserve the original attempt and the exact activity version. Refreshing resumes the same pending self-rating; do not generate a new answer after feedback has already been shown.
- A pattern match checks one narrow structure, not overall correctness or mastery. Unsupported errors require explicit self-review; never invent a pass/fail result, pronunciation score, or listening result from written text.
- The learner selects the rating even if it differs from the rule-match result. Explain the rating choices; do not silently alter the selection.
- The host uses pinned py-fsrs 6.3.2 with day-scale practice (no minute learning steps), deterministic intervals and a one-year cap. Store before/after state, the exact scheduler configuration, raw algorithm due date and the final planned date.
- Adaptive mode uses the selected desired retention. Fixed mode keeps FSRS evidence but uses the user's 1–60 day interval; Again schedules one day later. Future dates move forward to an allowed study day, never earlier than that mode's due instant.
- Preference changes apply to later ratings and do not hide existing due work. Retention is a scheduling target, not a measured probability of mastery.
- Reminders are opt-in, in-app only, at most once per local calendar date and only if active cards are due. Disabling reminders does not remove review cards. Archiving a memory suspends its card without erasing logs.

Implementation reference: [official py-fsrs package](https://pypi.org/project/fsrs/). Scheduling and persistence belong to the host, not the teaching prompt.
