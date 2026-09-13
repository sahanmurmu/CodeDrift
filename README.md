# CodeDrift

**CodeDrift** is a CLI tool that scans a project for outdated or overly
complex code patterns — and then uses AI to *contextually* judge whether
each finding is actually worth fixing, instead of blindly flagging
everything a rule matches.

## Why this exists

Two problems keep showing up in real codebases:

- **Legacy drift** — old projects keep running for years, and nobody
  tracks what's quietly become outdated in the language/ecosystem since
  the code was written.
- **Accidental complexity** — new code (especially AI-assisted or
  fast-written code) sometimes ends up more complex than it needs to be,
  when a simpler, more idiomatic pattern already exists.

Most linters just match rules blindly, whether or not the pattern was
intentional. CodeDrift adds a second layer: after a pattern is detected,
an AI reads the surrounding code and comments to decide if it's a real
issue or an intentional choice — and explains *why* either way.

## How it works

```
Project files
     │
     ▼
Rule-based detection  (scanner.py)
     │
     ▼
Group issues + build code context
     │
     ▼
Bulk request to Gemini  (advisor.py)
     │
     ▼
AI judges: worth changing? why? safe suggestion?
     │
     ▼
CLI report
```

Currently detection is rule-based (simple pattern matching for Python,
JS, and TS). Swapping this out for real linters (ESLint, Ruff) is on
the roadmap — see below.

## Requirements

- Python 3.9+
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free tier
  works, but is limited to **20 requests/day** for `gemini-3.6-flash`
  — see [Rate Limits](#rate-limits) below)

## Installation

```bash
git clone https://github.com/<your-username>/codedrift.git
cd codedrift
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_key_here
```

## Usage

```bash
python scanner.py /path/to/your/project
```

Or scan the current directory:

```bash
python scanner.py
```

### Sample output

```
============================================================
CODEDRIFT CLI REPORT
============================================================

📂 File: sample/legacy.js
------------------------------------------------------------

  [MEDIUM priority / LOW risk] Line 11 (1 related issues) | Confidence: 98%
     - var firstName = "Sahan";
     + const firstName = "Sahan";
     Changes:
       ✓ Replaced 'var' keyword with 'const'
     💡 Why should I care: Using 'var' can lead to scope hoisting bugs.
     📌 Priority: MEDIUM | Risk: Low
```

When AI decides a flagged pattern is intentional, it says so instead of
forcing a change:

```
   ✨ AI Skipped Line 4: The comment explicitly states that strict type
      matching via type() == int is required to reject subclasses like bool.
```

## Rate limits

The free Gemini API tier caps `gemini-3.6-flash` at **20 requests per
day** per project. CodeDrift sends the whole project in a single bulk
request per scan, so this is usually enough for a handful of scans a
day — but if you hit it, the tool will tell you clearly instead of
retrying uselessly. Options if you hit the limit:

- Wait for the daily quota to reset
- Enable billing on your Google AI Studio project for higher limits
- Switch to a lighter model

## Roadmap

- [ ] Replace hand-written pattern rules with real linters (ESLint for
      JS/TS, Ruff for Python) as the detection layer, keeping AI as the
      contextual judgment layer on top
- [ ] VS Code / browser extension wrapping the same core engine
- [ ] `fixer.py` — apply approved suggestions automatically

## License

MIT — see [LICENSE](LICENSE).