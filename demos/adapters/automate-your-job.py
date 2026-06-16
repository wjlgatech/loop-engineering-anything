"""CLI-Judge adapter for the ``automate-your-job`` demo (the standup-digest target).

Loaded by CLI-Judge via ``importlib``; exposes a module-level ``ADAPTER``. Shells
the target ``cli.py`` one-shot with no TTY and resolves the target directory from
``LOOPENG_PROOF_TARGET`` (the mutating workspace copy), so the same adapter grades
the baseline and every refined iteration.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from cli_judge.adapter import Adapter, Call, Result


class StandupAdapter:
    name = "automate-your-job"

    def _target(self) -> str:
        base = os.environ.get("LOOPENG_PROOF_TARGET", os.getcwd())
        return os.path.join(base, "cli.py")

    def invoke(self, call: Call) -> Result:
        env = dict(os.environ)
        env.update(call.env or {})
        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, self._target(), *call.argv],
                input=call.stdin or "",
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
        except OSError as e:
            return Result(exit_code=127, stdout="", stderr=f"failed to launch target: {e}",
                          duration_ms=(time.time() - t0) * 1000)
        return Result(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
                      duration_ms=(time.time() - t0) * 1000)


ADAPTER: Adapter = StandupAdapter()
