from __future__ import annotations

import io

import pytest

from diptrace_mcp.stdio_transport import write_payload


def test_payload_is_written_as_utf8_on_a_cp1251_text_stream() -> None:
    """Regression: catalog values contain "Ω", which cp1251 cannot encode."""

    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1251", newline="")
    try:
        write_payload('{"result": {"value": "10k\u03a9"}}', stream=stream)
    finally:
        stream.detach()

    assert raw.getvalue() == '{"result": {"value": "10k\u03a9"}}\n'.encode("utf-8")


def test_payload_adds_exactly_one_trailing_newline() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
    try:
        write_payload("{}", stream=stream)
    finally:
        stream.detach()

    assert raw.getvalue() == b"{}\n"


def test_payload_rejects_a_trailing_newline() -> None:
    with pytest.raises(ValueError):
        write_payload("{}\n", stream=io.StringIO())


def test_text_only_stream_is_supported() -> None:
    stream = io.StringIO()
    write_payload("plain", stream=stream)
    assert stream.getvalue() == "plain\n"
