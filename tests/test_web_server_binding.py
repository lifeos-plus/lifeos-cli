"""Tests for loopback binding detection and non-loopback warnings."""

from __future__ import annotations

from lifeos_web.server import is_loopback_host, warn_if_non_loopback_binding


def test_loopback_hosts_are_detected() -> None:
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("::1")
    assert is_loopback_host("127.0.0.2")


def test_non_loopback_hosts_are_detected() -> None:
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("192.168.1.10")
    assert not is_loopback_host("10.0.0.1")
    assert not is_loopback_host("example.com")


def test_loopback_binding_does_not_warn(capsys) -> None:
    warn_if_non_loopback_binding("127.0.0.1")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_non_loopback_binding_warns_on_stderr(capsys) -> None:
    warn_if_non_loopback_binding("0.0.0.0")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "0.0.0.0" in captured.err
    assert "Warning" in captured.err
