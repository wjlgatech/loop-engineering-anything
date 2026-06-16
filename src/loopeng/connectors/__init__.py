"""Connector (actuator) layer — loops act on external systems (U15, R8).

Connectors are the surface through which a loop *acts* on the outside world
(filing a report, opening a PR, posting a message). They are the prerequisite for
the org/individual rungs. Every connector sits behind the install/credential
isolation boundary (KTD8): structured (never shell-interpolated) payloads, a strict
allowlisted ``env=`` that drops ambient credentials, full 40-char commit-SHA pinning
for any install, and ``run_tool`` with ``shell=False`` + an args list.

This package is an *optional, injected* collaborator (KTD7): the loop controller
never imports it, so the System-1/System-2 flow gains no new mandatory branch.
"""

from __future__ import annotations

from .base import (
    Connector,
    ConnectorError,
    ConnectorResult,
    ConnectorSpec,
    MissingCredentialError,
    check_credentials,
    install_connector,
    validate_spec,
)
from .reference_connector import ReferenceFileReportConnector

__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectorResult",
    "ConnectorSpec",
    "MissingCredentialError",
    "check_credentials",
    "install_connector",
    "validate_spec",
    "ReferenceFileReportConnector",
]
