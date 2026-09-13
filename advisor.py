import os
import json
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-3.6-flash"

MAX_RETRIES = 5

RETRY_DELAYS = [3, 6, 9, 12, 15]


# ============================================================
# ERRORS
# ============================================================

class DailyQuotaExceededError(RuntimeError):
    """
    Raised when the free tier's per-day request quota is
    exhausted (GenerateRequestsPerDayPerProjectPerModel).

    This is NOT a transient error — retrying within the same
    run will not help, since the quota only resets the next
    day. Callers should surface this clearly instead of
    treating it like a normal rate-limit hiccup.
    """
    pass


# ============================================================
# GEMINI CLIENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set.\n"
        "Set your Gemini API key before running CodeDrift."
    )

client = genai.Client(api_key=API_KEY)


# ============================================================
# SYSTEM INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTION = """
You are CodeDrift, an expert code-modernization advisor.

Your job is NOT to blindly modernize code.

Static rules have already detected suspicious patterns.
Your job is to act as a strict contextual judge.

For every detected issue:

1. Read the provided code context carefully.
2. Locate the exact line identified by line_id.
3. Inspect surrounding code and comments.
4. Determine whether the detected pattern is actually worth changing.
5. DO NOT assume that modern code is always better.
6. Preserve intentional behavior.
7. If the developer intentionally used a pattern, do NOT recommend changing it.

Examples:

- type(x) == int may intentionally reject subclasses.
  In that case, do not replace it with isinstance().
- A simple use of var may be intentional depending on scope and compatibility.
- String concatenation may be clearer than a template literal in some situations.
- len(collection) may be intentionally used when the actual length is needed.

IMPORTANT:

You MUST inspect the provided code context before deciding.

Never judge an issue solely from the rule description.

If the issue is NOT worth changing:

"is_worth_changing": false

Explain why in "why_should_i_care".

If the issue IS genuinely worth changing:

"is_worth_changing": true

Provide a safe modernization.

Do not invent surrounding code.

Do not change behavior unnecessarily.

Return ONLY valid JSON.
"""


# ============================================================
# PROMPT BUILDER
# ============================================================

def build_bulk_prompt(bulk_payload):
    """
    Convert the scanner payload into a single AI prompt.
    """

    sections = []

    for file_name, file_data in bulk_payload.items():

        context = file_data.get(
            "context",
            "",
        )

        issues = file_data.get(
            "issues",
            [],
        )

        section = {
            "file_name": file_name,
            "code_context": context,
            "detected_issues": issues,
        }

        sections.append(section)

    payload_json = json.dumps(
        sections,
        indent=2,
        ensure_ascii=False,
    )

    return f"""
Analyze the following CodeDrift project findings.

The scanner has already detected potential issues.

You must independently judge whether each finding is genuinely
worth changing based on the supplied code context.

PROJECT FINDINGS:

{payload_json}


RETURN FORMAT:

Return a JSON object where each key is the exact file_name supplied
above.

Each file must contain an array of advice objects.

Example:

{{
  "src/example.py": [
    {{
      "line_id": 12,
      "is_worth_changing": true,
      "suggested_code": "if value in data:",
      "changes_made": [
        "Replaced deprecated dictionary membership method"
      ],
      "why_should_i_care": "This uses a removed/deprecated API.",
      "action_priority": "high",
      "risk": "low",
      "confidence": 0.97
    }}
  ]
}}

For an intentionally valid pattern:

{{
  "src/example.py": [
    {{
      "line_id": 20,
      "is_worth_changing": false,
      "suggested_code": "",
      "changes_made": [],
      "why_should_i_care": "The strict type check appears intentional because subclasses should not be accepted.",
      "action_priority": "none",
      "risk": "none",
      "confidence": 0.91
    }}
  ]
}}

RULES:

- Keep every line_id exactly as provided.
- Do not invent line IDs.
- Do not return findings for lines that were not supplied.
- Keep file names exactly unchanged.
- Return one advice object per supplied issue line when possible.
- suggested_code must contain only the replacement code, not explanations.
- changes_made must be a JSON array of strings.
- confidence must be between 0 and 1.
- is_worth_changing must be true or false.
- action_priority should be one of:
  "critical", "high", "medium", "low", "none".
- risk should describe the risk of making the suggested change:
  "high", "medium", "low", or "none".
- Return ONLY JSON.
"""


# ============================================================
# JSON CLEANER
# ============================================================

def parse_json_response(response_text):
    """
    Safely parse Gemini's JSON response.

    Handles accidental markdown code fences as well.
    """

    if not response_text:
        raise ValueError("AI returned an empty response.")

    text = response_text.strip()

    # Remove accidental markdown fences.
    if text.startswith("```"):

        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError as e:

        raise ValueError(
            f"AI returned invalid JSON: {e}"
        ) from e


# ============================================================
# RESPONSE VALIDATOR
# ============================================================

def validate_ai_results(
    ai_results,
    bulk_payload,
):
    """
    Validate and normalize Gemini's response.

    This prevents malformed AI output from breaking scanner.py.
    """

    if not isinstance(ai_results, dict):
        raise ValueError(
            "AI response must be a JSON object."
        )

    validated = {}

    for file_name, file_data in bulk_payload.items():

        raw_results = ai_results.get(
            file_name,
            [],
        )

        if not isinstance(raw_results, list):
            raw_results = []

        # Scanner knows the valid line IDs.
        valid_line_ids = {
            issue["line_id"]
            for issue in file_data.get(
                "issues",
                [],
            )
        }

        file_results = []

        for item in raw_results:

            if not isinstance(item, dict):
                continue

            line_id = item.get("line_id")

            if line_id not in valid_line_ids:
                continue

            # Normalize values.
            is_worth_changing = item.get(
                "is_worth_changing",
                True,
            )

            if not isinstance(
                is_worth_changing,
                bool,
            ):
                is_worth_changing = bool(
                    is_worth_changing
                )

            suggested_code = item.get(
                "suggested_code",
                "",
            )

            if suggested_code is None:
                suggested_code = ""

            changes_made = item.get(
                "changes_made",
                [],
            )

            if not isinstance(
                changes_made,
                list,
            ):
                changes_made = [str(changes_made)]

            confidence = item.get(
                "confidence",
                0,
            )

            if not isinstance(
                confidence,
                (int, float),
            ):
                confidence = 0

            # Clamp confidence to 0-1.
            confidence = max(
                0,
                min(1, float(confidence)),
            )

            normalized_item = {
                "line_id": line_id,

                "is_worth_changing":
                    is_worth_changing,

                "suggested_code":
                    str(suggested_code),

                "changes_made":
                    [str(x) for x in changes_made],

                "why_should_i_care":
                    str(
                        item.get(
                            "why_should_i_care",
                            "",
                        )
                    ),

                "action_priority":
                    str(
                        item.get(
                            "action_priority",
                            "unknown",
                        )
                    ).lower(),

                "risk":
                    str(
                        item.get(
                            "risk",
                            "unknown",
                        )
                    ).lower(),

                "confidence":
                    confidence,
            }

            file_results.append(
                normalized_item
            )

        validated[file_name] = file_results

    return validated


# ============================================================
# BULK ADVISOR
# ============================================================

def get_bulk_advice(
    bulk_payload,
    max_retries=MAX_RETRIES,
):
    """
    Send all project findings to Gemini in one request.

    Expected input:

    {
        "src/example.py": {
            "context": "...",
            "issues": [...]
        },

        "src/app.js": {
            "context": "...",
            "issues": [...]
        }
    }

    Returns:

    {
        "src/example.py": [
            {
                "line_id": 10,
                ...
            }
        ]
    }
    """

    if not bulk_payload:
        return {}

    prompt = build_bulk_prompt(
        bulk_payload
    )

    last_error = None

    for attempt in range(max_retries):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,

                contents=prompt,

                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,

                    response_mime_type="application/json",

                    temperature=0.1,
                ),
            )

            raw_text = getattr(
                response,
                "text",
                None,
            )

            ai_results = parse_json_response(
                raw_text
            )

            return validate_ai_results(
                ai_results,
                bulk_payload,
            )

        except Exception as e:

            last_error = e

            error_text = str(e).lower()

            # ------------------------------------------------
            # DAILY QUOTA EXHAUSTED
            # ------------------------------------------------
            #
            # Google's own "retry in Ns" hint on this error is
            # misleading for a *daily* quota — waiting 44s will
            # not bring it back. Detect it specifically and
            # fail immediately with a clear explanation instead
            # of burning through all our retries for nothing.

            is_daily_quota_error = (
                "perday" in error_text.replace("_", "")
                or "requests per day" in error_text
            )

            if is_daily_quota_error:

                limit_match = re.search(
                    r"limit:\s*'?(\d+)'?",
                    str(e),
                )

                limit_str = (
                    limit_match.group(1)
                    if limit_match
                    else "your"
                )

                raise DailyQuotaExceededError(
                    f"Daily free-tier request limit "
                    f"({limit_str} requests/day for "
                    f"{MODEL_NAME}) has been used up. "
                    f"This resets once a day — it will not "
                    f"help to retry right now. Either wait "
                    f"for the quota to reset, switch to a "
                    f"lighter model, or enable billing on "
                    f"the project for a higher limit."
                ) from e

            # Retry rate-limit / temporary errors.
            retryable = any(
                keyword in error_text
                for keyword in [
                    "429",
                    "resource_exhausted",
                    "rate limit",
                    "temporarily unavailable",
                    "503",
                    "deadline",
                    "timeout",
                ]
            )

            if not retryable:
                raise

            if attempt >= max_retries - 1:
                break

            delay = RETRY_DELAYS[
                min(
                    attempt,
                    len(RETRY_DELAYS) - 1,
                )
            ]

            print(
                f"⚠️ AI request temporarily unavailable. "
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

    raise RuntimeError(
        f"Gemini request failed after "
        f"{max_retries} attempts: {last_error}"
    )