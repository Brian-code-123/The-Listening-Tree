from __future__ import annotations

import os
import sys
from pathlib import Path
from textwrap import dedent


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: compose_playwright_comment.py <output-path>")
        return 1

    output_path = Path(sys.argv[1])
    status_line = os.environ.get("STATUS_LINE", "Status: UNKNOWN")
    report_url = os.environ.get("REPORT_URL", "")
    run_id = os.environ.get("RUN_ID", "")

    body = dedent(
        f"""\
        ### Playwright + Allure Report

        - {status_line}
        - Report URL: {report_url}
        - Workflow run: {run_id}

        ```mermaid
        flowchart TD
            A[Checkout repository] --> B[Install Python + Node]
            B --> C[Install Playwright browsers]
            C --> D[Start FastAPI server]
            D --> E[Run Playwright tests]
            E --> F[Generate Allure report]
            F --> G[Publish to GitHub Pages]
        ```

        The report includes screenshots and step-level traces captured by Allure.
        """
    ).strip() + "\n"

    output_path.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())