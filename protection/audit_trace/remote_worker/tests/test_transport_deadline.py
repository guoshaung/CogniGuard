"""No SSH or model calls: bounded channel-draining regression controls."""

from protection.audit_trace.remote_worker import transport


class FakeChannel:
    def __init__(self, out=b"", err=b"", finish=True):
        self.out, self.err = bytearray(out), bytearray(err)
        self.finish = finish
        self.closed = False
        self.exit_calls = 0

    def recv_ready(self):
        return bool(self.out)

    def recv_stderr_ready(self):
        return bool(self.err)

    def recv(self, n):
        part = bytes(self.out[:n])
        del self.out[:n]
        return part

    def recv_stderr(self, n):
        part = bytes(self.err[:n])
        del self.err[:n]
        return part

    def exit_status_ready(self):
        # Emulates a process unable to exit while either SSH stream is full.
        return self.finish and not self.out and not self.err

    def recv_exit_status(self):
        assert self.exit_status_ready(), "Must drain both streams before exit wait"
        self.exit_calls += 1
        return 0

    def close(self):
        self.closed = True


def test_full_streams_are_drained_with_bounded_retained_output():
    channel = FakeChannel(b"a" * 150000, b"sensitive stderr" * 20000)
    result = transport._collect_reply(channel, "fixture", transport.time.monotonic() + 2)
    assert result["status"] == "SUBMITTED"
    assert result["stdout_bytes"] == 150000 and result["stderr_bytes"] == 320000
    assert result["worker_reply"] == "a" * 65536 and result["stdout_truncated"]
    assert "sensitive" not in str(result)
    assert channel.exit_calls == 1 and not channel.out and not channel.err
    assert result["automatic_retry"] is False


def test_nonterminating_channel_deadline_returns_unknown_without_exit_wait(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        transport.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds)
    )
    channel = FakeChannel(b"partial", b"secret", finish=False)
    result = transport._collect_reply(channel, "fixture", 100.025)
    assert result["status"] == "SUBMITTED_OR_UNKNOWN"
    assert result["automatic_retry"] is False
    assert channel.closed and channel.exit_calls == 0
    assert result["worker_reply"] == "partial" and result["stderr_type_only"] == "PRESENT"


def test_infinite_output_cannot_evade_deadline(monkeypatch):
    now = [0.0]

    def tick():
        now[0] += 0.001
        return now[0]

    monkeypatch.setattr(transport.time, "monotonic", tick)
    channel = FakeChannel(finish=False)
    channel.recv_ready = lambda: True
    channel.recv = lambda n: b"x" * n
    result = transport._collect_reply(channel, "fixture", 0.01)
    assert result["status"] == "SUBMITTED_OR_UNKNOWN" and channel.closed
    assert len(result["worker_reply"]) <= 65536
    assert result["automatic_retry"] is False and channel.exit_calls == 0
