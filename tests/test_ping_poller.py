import pytest

from ping_poller import LATENCY_RE, ping


def test_regex_windows_normal():
    output = "Reply from 8.8.8.8: bytes=32 time=12ms TTL=118"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 12.0


def test_regex_windows_sub_1ms():
    output = "Reply from 8.8.8.8: bytes=32 time<1ms TTL=118"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 1.0


def test_regex_linux():
    output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.3 ms"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 12.3


def test_regex_no_match():
    output = "Request timed out."
    match = LATENCY_RE.search(output)
    assert match is None


def test_ping_returns_tuple():
    ok, ms = ping()
    assert isinstance(ok, bool)
    if ok:
        assert isinstance(ms, float)
    else:
        assert ms is None
