"""CLI-Judge adapter for the self-contained ``factcli`` proof target.

Self-contained by design: CLI-Judge loads this file via
``importlib`` and requires a module-level ``ADAPTER`` instance. It shells the
target ``cli.py`` one-shot with no TTY (stdin from the Call), and resolves the
target directory from ``LOOPENG_PROOF_TARGET`` (the mutating workspace copy) so
the same adapter grades the baseline and every refined iteration.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from cli_judge.adapter import Adapter, Call, Result


class FactCliAdapter:
    name = "factcli"

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


ADAPTER: Adapter = FactCliAdapter()
