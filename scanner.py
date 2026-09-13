from collections import defaultdict
from pathlib import Path
import sys

from advisor import get_bulk_advice, DailyQuotaExceededError
import ast_helper


# ============================================================
# CONFIGURATION
# ============================================================

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
}

IGNORE_FILES = {
    "scanner.py",
    "advisor.py",
    "fixer.py",
    "ast_helper.py",
}

TARGET_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
}


# ============================================================
# RULES
# ============================================================

RULES = {

    ".py": [
        {
            "rule_id": "PY001",
            "name": "deprecated_has_key",
            "category": "modernization",
            "pattern": ".has_key(",
            "severity": "high",
            "replacement": "'in' operator",
            "reason": (
                "Deprecated dictionary method (.has_key() is removed "
                "in modern Python)"
            ),
        },

        {
            "rule_id": "PY002",
            "name": "legacy_string_formatting",
            "category": "modernization",
            "pattern": "%",
            "severity": "low",
            "replacement": "f-strings",
            "reason": (
                "Legacy % string formatting "
                "(prefer f-strings in modern Python)"
            ),
        },

        {
            "rule_id": "PY003",
            "name": "strict_type_check",
            "category": "best_practice",
            "pattern": "type(",
            "severity": "medium",
            "replacement": "isinstance()",
            "reason": (
                "Direct type comparison using type() "
                "(prefer isinstance() unless strict matching is required)"
            ),
        },

        {
            "rule_id": "PY004",
            "name": "empty_collection_check",
            "category": "idiom",
            "pattern": "len(",
            "severity": "low",
            "replacement": "if not collection:",
            "reason": (
                "Checking empty collection using len() == 0 "
                "(prefer truthiness check)"
            ),
        },
    ],

    ".js": [
        {
            "rule_id": "JS001",
            "name": "var_usage",
            "category": "modernization",
            "pattern": "var ",
            "severity": "medium",
            "replacement": "let / const",
            "reason": (
                "Outdated 'var' keyword used "
                "(function-scoped and prone to hoisting)"
            ),
        },

        {
            "rule_id": "JS002",
            "name": "string_concatenation",
            "category": "modernization",
            "pattern": " + ",
            "severity": "low",
            "replacement": "Template literals (`...`)",
            "reason": (
                "String concatenation using + operator "
                "(prefer template literals)"
            ),
        },

        {
            "rule_id": "JS003",
            "name": "anonymous_functions",
            "category": "modernization",
            "pattern": "function(",
            "severity": "low",
            "replacement": "Arrow functions (() => {})",
            "reason": (
                "Anonymous function expression used "
                "(prefer modern arrow functions)"
            ),
        },
    ],

    ".ts": [
        {
            "rule_id": "TS001",
            "name": "var_usage",
            "category": "modernization",
            "pattern": "var ",
            "severity": "medium",
            "replacement": "let / const",
            "reason": "Outdated 'var' keyword used in TypeScript",
        },
    ],
}


# ============================================================
# FILE SCANNER
# ============================================================

def collect_file_issues_grouped(file_path):
    """
    Scan one file and group all detected issues by line number.

    Returns:
        [
            {
                "line_id": 10,
                "code": "some code...",
                "detected_issues": [
                    "[PY003] Direct type comparison..."
                ],
                "raw_severities": [
                    "medium"
                ]
            }
        ]
    """

    suffix = file_path.suffix.lower()

    if suffix not in RULES:
        return []

    line_groups = defaultdict(
        lambda: {
            "code": "",
            "issues": [],
            "severities": [],
        }
    )

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:

            for line_no, line in enumerate(f, start=1):

                clean_line = line.strip()

                # Ignore comments
                if clean_line.startswith(("#", "//")):
                    continue

                for rule in RULES[suffix]:

                    if rule["pattern"] in clean_line:

                        line_groups[line_no]["code"] = clean_line

                        issue_text = (
                            f"[{rule['rule_id']}] "
                            f"{rule['reason']}"
                        )

                        line_groups[line_no]["issues"].append(
                            issue_text
                        )

                        line_groups[line_no]["severities"].append(
                            rule["severity"]
                        )

    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return []

    # Convert grouped dictionary into a list.
    formatted_groups = []

    for line_no, data in sorted(line_groups.items()):

        formatted_groups.append(
            {
                "line_id": line_no,
                "code": data["code"],
                "detected_issues": data["issues"],
                "raw_severities": data["severities"],
            }
        )

    return formatted_groups


# ============================================================
# CONTEXT BUILDER
# ============================================================

def build_file_context(file_path, grouped_issues):
    """
    Build the code context that will be sent to Gemini.

    Python:
        Use AST helper to extract relevant surrounding code.

    JS/TS:
        Send the full file for now.
    """

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:
            full_content = f.read()

    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return ""

    # Python gets AST-based context.
    if file_path.suffix.lower() == ".py":

        unique_contexts = set()

        for issue in grouped_issues:

            try:
                context = ast_helper.get_python_context(
                    full_content,
                    issue["line_id"],
                )

                if context:
                    unique_contexts.add(context)

            except Exception as e:
                print(
                    f"⚠️ AST context error "
                    f"in {file_path}:{issue['line_id']} - {e}"
                )

        if unique_contexts:

            return (
                "\n\n"
                "... [Other Code Hidden] ..."
                "\n\n"
            ).join(unique_contexts)

    # JS / TS / fallback
    return full_content


# ============================================================
# PROJECT SCANNER
# ============================================================

def scan_project(directory):
    """
    Scan the complete project.

    Flow:

        Project
           ↓
        Rule detection
           ↓
        Group issues
           ↓
        Build context
           ↓
        Bulk AI request
           ↓
        AI judgement
           ↓
        CLI report
    """

    path = Path(directory)

    if not path.exists():
        print(f"❌ Directory does not exist: {directory}")
        return

    if not path.is_dir():
        print(f"❌ Not a directory: {directory}")
        return

    print()
    print("=" * 60)
    print("CODEDRIFT SCANNER")
    print("=" * 60)
    print(f"📂 Project: {path.resolve()}")
    print()

    bulk_payload = {}

    total_files = 0
    total_issues = 0

    # --------------------------------------------------------
    # 1. FIND AND SCAN FILES
    # --------------------------------------------------------

    for file_path in path.rglob("*"):

        # Skip directories that should never be scanned.
        if any(
            ignored_dir in file_path.parts
            for ignored_dir in IGNORE_DIRS
        ):
            continue

        if not file_path.is_file():
            continue

        if file_path.name in IGNORE_FILES:
            continue

        if file_path.suffix.lower() not in TARGET_EXTENSIONS:
            continue

        total_files += 1

        grouped_issues = collect_file_issues_grouped(file_path)

        if not grouped_issues:
            continue

        total_issues += len(grouped_issues)

        context = build_file_context(
            file_path,
            grouped_issues,
        )

        if not context:
            continue

        # IMPORTANT:
        # Use relative path instead of only file.name.
        # Otherwise:
        # tests/app.py
        #
        # would overwrite each other.
        relative_path = str(
            file_path.relative_to(path)
        )

        bulk_payload[relative_path] = {
            "context": context,
            "issues": grouped_issues,
        }

    # --------------------------------------------------------
    # 2. NOTHING FOUND
    # --------------------------------------------------------

    if not bulk_payload:

        print("✅ No issues found in the project!")
        print()
        return

    # --------------------------------------------------------
    # 3. BULK AI REQUEST
    # --------------------------------------------------------

    print(
        f"⚡ Found {total_issues} issue groups "
        f"across {len(bulk_payload)} files."
    )

    print(
        "🤖 Sending project findings to AI in one bulk request..."
    )

    print()

    try:
        ai_results = get_bulk_advice(bulk_payload)

    except DailyQuotaExceededError as e:

        print()
        print("⏳ Daily AI quota used up.")
        print(f"   {e}")
        print()

        return

    except Exception as e:

        print()
        print("❌ AI request failed.")
        print(f"   Error: {e}")
        print()

        return

    # Make sure we always have a dictionary.
    if not isinstance(ai_results, dict):

        print("❌ AI returned an invalid response format.")
        print()

        return

    # --------------------------------------------------------
    # 4. REPORT
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("CODEDRIFT CLI REPORT")
    print("=" * 60)
    print()

    total_real_issues = 0
    total_ai_skipped = 0

    for file_name, data in bulk_payload.items():

        file_issues = data["issues"]

        # AI response for this file.
        file_ai_responses = ai_results.get(
            file_name,
            [],
        )

        if not isinstance(file_ai_responses, list):
            file_ai_responses = []

        # Map:
        #
        # line_id → AI response
        #
        ai_map = {}

        for item in file_ai_responses:

            if not isinstance(item, dict):
                continue

            line_id = item.get("line_id")

            if line_id is None:
                continue

            ai_map[line_id] = item

        # ----------------------------------------------------
        # Match scanner findings with AI findings.
        # ----------------------------------------------------

        issues_to_print = []

        for issue in file_issues:

            line_id = issue["line_id"]

            advice = ai_map.get(line_id)

            # If AI didn't return an answer for this line,
            # don't blindly call it a real issue.
            if advice is None:
                continue

            is_skipped = not advice.get(
                "is_worth_changing",
                True,
            )

            issues_to_print.append(
                (
                    issue,
                    advice,
                    is_skipped,
                )
            )

        # ----------------------------------------------------
        # Count real issues.
        # ----------------------------------------------------

        real_issues = [
            item
            for item in issues_to_print
            if not item[2]
        ]

        skipped_issues = [
            item
            for item in issues_to_print
            if item[2]
        ]

        total_real_issues += len(real_issues)
        total_ai_skipped += len(skipped_issues)

        # Only skip the file entirely if AI gave us nothing to
        # show for it at all (no matching advice for any issue).
        # A file where AI skipped every issue should still be
        # shown, so the user can see *why* nothing changed there.
        if not issues_to_print:
            continue

        print(f"📂 File: {file_name}")
        print("-" * 60)
        print()

        if not real_issues:
            print(
                f"   (All {len(skipped_issues)} detected "
                f"issue(s) were skipped by AI — no changes "
                f"needed)"
            )
            print()

        for issue, advice, is_skipped in issues_to_print:

            line_id = issue["line_id"]

            # ------------------------------------------------
            # AI SKIPPED
            # ------------------------------------------------

            if is_skipped:

                total_ai_skipped += 0  # already counted above

                why = advice.get(
                    "why_should_i_care",
                    "AI decided this change is not necessary.",
                )

                print(
                    f"   ✨ AI Skipped Line {line_id}: {why}"
                )

                print()

                continue

            # ------------------------------------------------
            # CONFIDENCE
            # ------------------------------------------------

            confidence_value = advice.get(
                "confidence",
                0,
            )

            if isinstance(
                confidence_value,
                (int, float),
            ):

                # Handle both:
                #
                # 0.85
                # 85
                #
                if 0 <= confidence_value <= 1:
                    confidence_percent = int(
                        confidence_value * 100
                    )
                else:
                    confidence_percent = int(
                        confidence_value
                    )

            else:
                confidence_percent = 0

            # Keep confidence sane.
            confidence_percent = max(
                0,
                min(100, confidence_percent),
            )

            risk = str(
                advice.get(
                    "risk",
                    "UNKNOWN",
                )
            ).upper()

            priority = str(
                advice.get(
                    "action_priority",
                    "UNKNOWN",
                )
            ).upper()

            # ------------------------------------------------
            # MAIN ISSUE
            # ------------------------------------------------

            print(
                f"  [{priority} priority / {risk} risk] "
                f"Line {line_id} "
                f"({len(issue['detected_issues'])} "
                f"related issues) "
                f"| Confidence: {confidence_percent}%"
            )

            # Original code
            print(
                f"     - {issue['code']}"
            )

            # Suggested replacement
            suggested_code = advice.get(
                "suggested_code",
                "",
            )

            if suggested_code:

                print(
                    f"     + {suggested_code}"
                )

            # ------------------------------------------------
            # CHANGES
            # ------------------------------------------------

            changes = advice.get(
                "changes_made",
                [],
            )

            if isinstance(changes, list) and changes:

                print("     Changes:")

                for change in changes:

                    print(
                        f"       ✓ {change}"
                    )

            # ------------------------------------------------
            # WHY
            # ------------------------------------------------

            why = advice.get(
                "why_should_i_care",
                "",
            )

            if why:

                print(
                    f"     💡 Why should I care: {why}"
                )

            # ------------------------------------------------
            # PRIORITY / RISK
            # ------------------------------------------------

            risk_title = str(
                advice.get(
                    "risk",
                    "UNKNOWN",
                )
            ).title()

            print(
                f"     📌 Priority: {priority} "
                f"| Risk: {risk_title}"
            )

            print()

    # --------------------------------------------------------
    # 5. SUMMARY
    # --------------------------------------------------------

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(
        f"📁 Files scanned: {total_files}"
    )

    print(
        f"🔎 Issue groups detected: {total_issues}"
    )

    print(
        f"🤖 AI-approved changes: {total_real_issues}"
    )

    print(
        f"✨ AI-skipped issues: {total_ai_skipped}"
    )

    print()


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":

    target_directory = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "."
    )

    scan_project(target_directory)