"""Tests for loopback, specific-address, and wildcard binding behavior."""

from __future__ import annotations

import pytest

from lifeos_cli.config import ConfigurationError
from lifeos_web.server import (
    is_all_interfaces_host,
    is_loopback_host,
    validate_web_binding_host,
    warn_if_non_loopback_binding,
)


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
    warn_if_non_loopback_binding("192.0.2.10")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "192.0.2.10" in captured.err
    assert "Warning" in captured.err


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "0:0:0:0:0:0:0:0"])
def test_all_interfaces_binding_is_rejected(host: str) -> None:
    with pytest.raises(ConfigurationError, match="specific LAN or Tailscale address"):
        validate_web_binding_host(host)


def test_specific_external_binding_is_allowed_with_warning(capsys) -> None:
    assert not is_all_interfaces_host("192.0.2.10")

    validate_web_binding_host("192.0.2.10")

    captured = capsys.readouterr()
    assert "192.0.2.10" in captured.err
    assert "Warning" in captured.err
