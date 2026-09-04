# scripts/regenerate_resume.py

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # allow direct invocation

import argparse
import json
from app.services.markdown_rebuild_service import (
    regenerate_resume
)

# =========================================================
# CLI
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Regenerate resume artifacts "
            "from editable markdown."
        )
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        help="Variant output directory"
    )

    args = parser.parse_args()

    result = regenerate_resume(
        output_dir=args.output_dir
    )

    # print(json.dumps(result, indent=2))
    

    print("\n💕 Regeneration complete.\n")

    for key, value in result["artifacts"].items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()