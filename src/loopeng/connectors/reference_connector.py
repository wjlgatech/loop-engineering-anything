"""Reference connector — demonstrates the actuator surface (U15, R8).

``ReferenceFileReportConnector`` "files a research report" to an external system.
It exists to exercise the isolation boundary end to end:

  - it declares a capability (``"file_report"``) and a required credential name;
  - ``act`` gates on the credential (name only, never the value) and canonicalizes
    the **structured** payload -- it never builds a shell string;
  - the (illustrative) delivery step would go through ``run_tool`` with an args
    list, so a metacharacter-laden ``title``/``body`` value can never reach a shell.

For tests we round-trip the structured payload rather than hitting a real network
(KTD9 skip-not-fail): the boundary -- credential gate, structured handling, no
shell -- is what's under test, not a live endpoint.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ..adapters.safety import run_tool
from .base import Connector, ConnectorResult, check_credentials

# The credential name the connector reads from the environment (never logged).
_REPORT_TOKEN_ENV = "LOOPENG_REPORT_TOKEN"


@dataclass(frozen=True)
class ReferenceFileReportConnector:
    """Files a structured research report. Implements the ``Connector`` protocol.

    ``endpoint`` is the (pinned) destination the report would be delivered to;
    ``dry_run`` keeps the round-trip in-process for tests so no network is hit.
    """

    endpoint: str = "https://reports.example.invalid/v1/file"
    dry_run: bool = True

    @property
    def name(self) -> str:
        return "reference-file-report"

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("file_report",)

    @property
    def required_env(self) -> tuple[str, ...]:
        return (_REPORT_TOKEN_ENV,)

    def act(self, payload: dict) -> ConnectorResult:
        """File a report described by the structured ``payload``.

        ``payload`` must carry ``action == "file_report"`` plus ``title`` and
        ``body``. The credential gate runs first (fails fast by NAME). The payload
        is serialized as structured JSON and passed as a single args-list element
        to ``run_tool`` -- never interpolated into a command string -- so shell
        metacharacters in any field are inert.
        """
        try:
            check_credentials(self.required_env)
        except Exception as exc:  # MissingCredentialError -- message is name-only
            return ConnectorResult(False, error=str(exc))

        if payload.get("action") != "file_report":
            return ConnectorResult(
                False, error=f"unsupported action: {payload.get('action')!r}"
            )
        title = payload.get("title")
        body = payload.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            return ConnectorResult(False, error="payload requires string 'title' and 'body'")

        # Structured, never shell-interpolated. The token is read from the env and
        # passed by name to the child; it is not placed in the canonical record.
        canonical = {
            "action": "file_report",
            "endpoint": self.endpoint,
            "title": title,
            "body": body,
        }
        record = json.dumps(canonical, sort_keys=True)

        if self.dry_run:
            # In-process round-trip: the boundary, not a live endpoint, is the SUT.
            return ConnectorResult(True, detail=canonical)

        # Live path (not exercised in tests): the payload travels as ONE args-list
        # element -- shell=False means metacharacters in it are never interpreted.
        token = os.environ[_REPORT_TOKEN_ENV]
        res = run_tool(
            ["curl", "-sS", "-H", f"Authorization: Bearer {token}", "--data-binary", record, self.endpoint],
            timeout=60,
        )
        if not res.ok:
            return ConnectorResult(False, detail=canonical, error="delivery failed")
        return ConnectorResult(True, detail=canonical)


# Static assertion: the reference connector satisfies the protocol.
_PROTOCOL_CHECK: Connector = ReferenceFileReportConnector()
