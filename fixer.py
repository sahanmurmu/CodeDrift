import json
from pathlib import Path

def apply_fixes(report_file="codedrift_report.json"):
    report_path = Path(report_file)
    if not report_path.exists():
        print(f"Report file '{report_file}' nahi mili! Pehle scanner run karo.")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for file_info in data.get("results", []):
        target_file = Path(file_info["file"])
        if not target_file.exists():
            continue

        # Read the file's lines into memory
        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        modified = False

        for finding in file_info["findings"]:
            line_idx = finding["line"] - 1
            orig = finding["original_code"]
            fix = finding["suggested_fix"]

            print("\n" + "-"*40)
            print(f"File: {target_file} (Line {finding['line']})")
            print(f"  - {orig}")
            print(f"  + {fix}")
            print(f"Reason: {finding['reason']}")

            choice = input("\n👉 Apply this fix? [y/N]: ").strip().lower()

            if choice == "y":
                # Replace the line, preserving the original indentation
                current_line = lines[line_idx]
                indent = current_line[:len(current_line) - len(current_line.lstrip())]
                lines[line_idx] = indent + fix.strip() + "\n"
                modified = True
                print("✔ Change staged!")
            else:
                print("Skipped.")

        # If any change was accepted, write the file back
        if modified:
            with open(target_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"\n✅ {target_file} updated successfully!")

if __name__ == "__main__":
    apply_fixes()