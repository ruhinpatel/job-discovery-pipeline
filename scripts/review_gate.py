"""Human review gate: the human-in-the-loop as a visible pipeline step.

Why this exists: the pipeline only ORDERS candidate postings. Nothing it
produces may trigger an application or outreach on its own. This script makes
that rule an explicit stage: it surfaces the ranked queue and states that a
person must review and approve before any downstream action.

Runs only over committed synthetic fixtures; no network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    # Same shim as candidate_queue.py: add src/ so `pipeline` is importable.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pipeline.candidate_queue import build_queue, format_queue

NOTICE = """\
================ HUMAN REVIEW REQUIRED ================
In a real deployment, a person must review and approve this queue before
ANY downstream action (submitting an application or sending outreach).
This gate is an intentional stop point. Nothing past here runs automatically.
(Demo: synthetic data only; this gate is a no-op and exits 0.)
=======================================================
"""


def main() -> int:
    print(format_queue(build_queue()))
    print()
    print(NOTICE)
    # Production wiring: make this step a job bound to a GitHub Environment
    # with required reviewers; downstream jobs `needs:` it, so the workflow
    # pauses until a reviewer approves. The demo gate only surfaces the queue.
    return 0


if __name__ == "__main__":
    sys.exit(main())
