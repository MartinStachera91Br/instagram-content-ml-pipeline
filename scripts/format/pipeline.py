"""
Format Analysis Pipeline — Orchestrator.

CLI with 4 commands reflecting the human-in-the-loop flow:

    python -m scripts.format.pipeline discover   # Phase 1: AI proposes -> review.md
    python -m scripts.format.pipeline confirm     # Phase 1.5: Parse review.md -> reference.json
    python -m scripts.format.pipeline extract     # Phase 2: Extract features for all posts
    python -m scripts.format.pipeline all         # Runs discover only (confirm requires human)
"""

import json
import re
import sys

from scripts.config import (
    FORMAT_FEATURES_REVIEW_MD,
    FORMAT_FEATURES_REF,
)


# =========================================================================
# Phase 1.5 — Confirm: parse review.md into reference.json
# =========================================================================

def _parse_review_markdown(text: str) -> list[dict]:
    """
    Parse format_features_review.md back into structured feature dicts.

    Expected structure per feature:
        ## N. feature_name
        **Description:** ...
        **Type:** categorical | numeric | boolean | multi-select
        **Categories:** / **Scale:** / **Values:**
        - `value` -- description
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sections = re.split(r"\n-{3,}\n", text)
    features = []
    errors = []

    for section in sections:
        section = section.strip()
        header_match = re.search(r"^##\s+\d+\.\s+(\S+)", section, re.MULTILINE)
        if not header_match:
            continue

        name = header_match.group(1).strip()

        desc_match = re.search(r"\*\*Description:\*\*\s*(.+)", section)
        description = desc_match.group(1).strip() if desc_match else ""

        type_match = re.search(r"\*\*Type:\*\*\s*(.+)", section)
        ftype = type_match.group(1).strip().lower() if type_match else "categorical"

        values = []
        value_lines = re.findall(r"^-\s+`([^`]+)`(?:[ \t]*-{1,2}[ \t]*(.*))?$", section, re.MULTILINE)
        for val, desc in value_lines:
            entry = {"value": val.strip()}
            if desc.strip():
                entry["description"] = desc.strip()
            values.append(entry)

        if len(values) < 2:
            errors.append(f"Feature '{name}': needs at least 2 categories/scale points, found {len(values)}")
            continue

        if not description:
            errors.append(f"Feature '{name}': missing description")
            continue

        feature = {
            "name": name,
            "description": description,
            "type": ftype,
            "possible_values": values,
        }
        features.append(feature)

    return features, errors


def run_confirm():
    """Phase 1.5: parse the review file and save as format_features_reference.json."""
    if not FORMAT_FEATURES_REVIEW_MD.exists():
        print(f"[confirm] Review file not found: {FORMAT_FEATURES_REVIEW_MD}")
        print("Run 'python -m scripts.format.pipeline discover' first.")
        sys.exit(1)

    text = FORMAT_FEATURES_REVIEW_MD.read_text(encoding="utf-8")
    features, errors = _parse_review_markdown(text)

    if errors:
        print(f"[confirm] Parsing errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
        print("\nFix the issues in format_features_review.md and re-run confirm.")
        sys.exit(1)

    if not features:
        print("[confirm] No features found in the review file.")
        sys.exit(1)

    ref_data = {
        "title": "Format-Specific Features",
        "description": "Features specific to this content format, proposed by AI and confirmed by human.",
        "feature_count": len(features),
        "features": features,
    }

    FORMAT_FEATURES_REF.write_text(
        json.dumps(ref_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[confirm] {len(features)} features confirmed.")
    print(f"[confirm] Saved: {FORMAT_FEATURES_REF}")
    print(f"\nReady for extraction. Run: python -m scripts.format.pipeline extract")


# =========================================================================
# Main CLI
# =========================================================================

def main():
    commands = {
        "discover": "Phase 1: AI proposes features -> review.md",
        "confirm": "Phase 1.5: Parse review.md -> reference.json",
        "extract": "Phase 2: Extract format features for all posts",
        "all": "Run discover (confirm requires human review)",
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Format Analysis Pipeline")
        print("=" * 40)
        print("\nUsage: python -m scripts.format.pipeline <command>\n")
        print("Commands:")
        for cmd, desc in commands.items():
            print(f"  {cmd:12s} {desc}")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "discover":
        from scripts.format.discover_features import run_discovery
        run_discovery()

    elif cmd == "confirm":
        run_confirm()

    elif cmd == "extract":
        from scripts.format.extractor import run_format_extraction
        force = "--force" in sys.argv
        run_format_extraction(force=force)

    elif cmd == "all":
        from scripts.format.discover_features import run_discovery
        run_discovery()
        print("\n" + "=" * 50)
        print("Discovery complete. Review format_features_review.md")
        print("Then run: python -m scripts.format.pipeline confirm")


if __name__ == "__main__":
    main()
