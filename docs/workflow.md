# Agent Workflow Design

## Agent 1: Example Search Agent

**Responsibility:** Build a vocabulary card from authentic English sources.

**Input:** `add sanction`

**Output:** Saved vocabulary record with example sentence, Chinese translation, source name, source URL, tutor metadata, and review schedule.

```text
User input
  -> Parse command
  -> Search trusted English news with Tavily
  -> Select article from Reuters/BBC/AP/Guardian/NPR/NYT-style sources
  -> Extract a sentence containing the target word
  -> Generate Chinese translation and tutor metadata with Qwen
  -> Save record to SQLite
  -> Create spaced repetition review state
  -> Return result to web UI or Telegram/OpenClaw
```

Stored fields include:

- Word
- Phonetic symbol
- Part of speech
- Chinese meaning
- English definition
- Example sentence
- Chinese translation
- Source name
- Source URL
- Source type: `authentic` or `ai_fallback`
- Collocations
- Synonyms
- Antonyms
- Memory tip
- Difficulty
- Tags
- Review status

If no external article is available, the system may save an AI fallback example, but it is marked as `source_type=ai_fallback` and does not pretend to be a real source.

## Agent 2: Vocabulary Tutor Agent

**Responsibility:** Generate study metadata for each word.

```text
Word + example sentence
  -> Qwen vocabulary analysis
  -> IPA / POS / definitions
  -> Collocations / synonyms / antonyms
  -> Memory tip and difficulty
  -> Store and display in word detail page
```

## Review Workflow

```text
Saved word
  -> Review table initialized
  -> User marks Again or Good
  -> Ease factor and interval update
  -> Review history saved
  -> Learning records updated
```

## IM Workflow

Telegram messages enter the `/telegram/webhook` route. OpenClaw-style gateway messages enter `/openclaw/gateway`. Both paths execute the same agent/database workflow used by the web UI.

Supported demo commands:

```text
add abandon
query abandon
update abandon | exam word
review
quiz
stats
delete abandon
```
