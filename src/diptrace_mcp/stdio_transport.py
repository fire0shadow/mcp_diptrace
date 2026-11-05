"""UTF-8 safe writing for the MCP stdio transport.

The MCP stdio transport is defined in terms of UTF-8 encoded JSON-RPC lines.
Python does not guarantee that for ``sys.stdout``: on Windows the stream uses
the ANSI code page of the process (for example cp1251 on a Russian system), so
writing a payload that contains a character outside that code page raises
``UnicodeEncodeError``. For this server that is fatal, because a single
catalog value such as ``10kΩ`` is enough to tear down the whole process while
it is serialising a normal tool response.

Writing the already encoded UTF-8 bytes to the underlying binary buffer keeps
the wire format independent of the console code page.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO


def write_payload(payload: str, *, stream: TextIO | None = None) -> None:
    """Write one JSON-RPC payload as a single UTF-8 line.

    ``payload`` must not contain a trailing newline; exactly one is added.
    When the stream exposes a binary buffer the bytes are written unchanged,
    otherwise the text stream is used as a best-effort fallback.
    """

    if payload.endswith("\n"):
        raise ValueError("payload must not contain a trailing newline")
    target: Any = sys.stdout if stream is None else stream
    data = (payload + "\n").encode("utf-8")
    binary = getattr(target, "buffer", None)
    if binary is not None:
        binary.write(data)
        binary.flush()
        return
    target.write(payload + "\n")
    target.flush()
