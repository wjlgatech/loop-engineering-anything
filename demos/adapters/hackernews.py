"""CLI-Judge adapter for the Printing-Press `hackernews` CLI (proof target).

Self-contained (CLI-Judge loads this file standalone and requires a module-level
``ADAPTER``). Mirrors the reference ``pp_cli_adapter``: one-shot, no TTY, replay
routed via base-url env names, non-zero exit captured not raised. Resolve the
binary from ``LOOPENG_PROOF_BINARY`` (or the adopted tool on PATH); absent it the
adapter skips cleanly (exit 127).
"""
from __future__ import annotations

import os
import subprocess
import time

from cli_judge.adapter import Adapter, Call, Result

DEFAULT_BINARY = "hackernews"
_BASE_URL_ENVS = ["API_BASE_URL", "BASE_URL", "PP_BASE_URL", "HN_BASE_URL"]


class HackerNewsAdapter:
    name = "hackernews"

    def _binary(self) -> str:
        return os.environ.get("LOOPENG_PROOF_BINARY", DEFAULT_BINARY)

    def invoke(self, call: Call) -> Result:
        binary = self._binary()
        env = dict(os.environ)
        env.update(call.env)
        if call.replay_base_url:
            for name in _BASE_URL_ENVS:
                env[name] = call.replay_base_url
        t0 = time.time()
        try:
            proc = subprocess.run(
                [binary, *call.argv], input=call.stdin or "",
                capture_output=True, text=True, env=env,
            )
        except OSError as e:
            return Result(exit_code=127, stdout="", stderr=f"failed to launch {binary}: {e}",
                          duration_ms=(time.time() - t0) * 1000)
        return Result(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
                      duration_ms=(time.time() - t0) * 1000)


ADAPTER: Adapter = HackerNewsAdapter()
