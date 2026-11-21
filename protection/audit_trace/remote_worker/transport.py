"""SSH/SFTP task transport. Credentials stay in memory; no implicit execution retry."""

from __future__ import annotations

import json
import shlex
import time
from dataclasses import dataclass
from pathlib import PurePosixPath

from .protocol import Task, canonical, digest


def _collect_reply(channel, task_id: str, deadline: float) -> dict:
    """Drain both SSH streams without waiting on a possibly blocked exit status.

    Only bounded stdout is retained; excess bytes are drained and discarded.
    Closing an expired channel does not prove whether its remote job finished.
    The durable job claim must be polled, never regenerated automatically.
    """
    output = bytearray()
    stdout_bytes = stderr_bytes = 0
    limit = 65536
    while time.monotonic() < deadline:
        progressed = False
        if channel.recv_ready():
            chunk = channel.recv(16384)
            stdout_bytes += len(chunk)
            output.extend(chunk[: max(0, limit - len(output))])
            progressed = bool(chunk)
        if channel.recv_stderr_ready():
            chunk = channel.recv_stderr(16384)
            stderr_bytes += len(chunk)
            progressed = progressed or bool(chunk)
        if (
            channel.exit_status_ready()
            and not channel.recv_ready()
            and not channel.recv_stderr_ready()
        ):
            status = channel.recv_exit_status()  # Ready and both streams already drained.
            return {
                "status": "SUBMITTED" if status >= 0 else "SUBMITTED_OR_UNKNOWN",
                "task_id": task_id,
                "exit_status": status,
                "worker_reply": output.decode(errors="replace"),
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
                "stdout_truncated": stdout_bytes > limit,
                "stderr_type_only": "PRESENT" if stderr_bytes else "EMPTY",
                "automatic_retry": False,
            }
        if not progressed:
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    channel.close()
    return {
        "status": "SUBMITTED_OR_UNKNOWN",
        "task_id": task_id,
        "reason": "SSH_REPLY_DEADLINE_POLL_ONLY",
        "automatic_retry": False,
        "worker_reply": output.decode(errors="replace"),
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        "stdout_truncated": stdout_bytes > limit,
        "stderr_type_only": "PRESENT" if stderr_bytes else "EMPTY",
    }


@dataclass(frozen=True)
class RemoteConfig:
    host: str
    port: int
    username: str
    host_fingerprint: str
    python: str
    workdir: str
    model_dir: str
    model_manifest: str

    def validate(self) -> None:
        if not self.host or not 1 <= self.port <= 65535 or not self.username:
            raise ValueError("Invalid SSH target")
        if not self.host_fingerprint.startswith("SHA256:"):
            raise ValueError("Pin the observed/verified SSH host key")
        for value in (self.python, self.workdir, self.model_dir, self.model_manifest):
            path = PurePosixPath(value)
            if not path.is_absolute() or ".." in path.parts or any(c in value for c in "\r\n\0"):
                raise ValueError("Explicit safe absolute Linux paths required")


class SSHTransport:
    def __init__(self, config: RemoteConfig, client):
        config.validate()
        from .preflight import fingerprint

        actual = fingerprint(client.get_transport().get_remote_server_key())
        if actual != config.host_fingerprint:
            raise ValueError("SSH fingerprint mismatch")
        self.config = config
        self.client = client

    def command(self, task: Task) -> str:
        task.validate()
        c = self.config
        path = str(PurePosixPath(c.workdir) / "inbox" / (task.task_id + ".json"))
        args = [
            c.python,
            "-B",
            "-m",
            "protection.audit_trace.remote_worker.worker",
            "--task",
            path,
            "--spool",
            str(PurePosixPath(c.workdir) / "jobs"),
            "--model-dir",
            c.model_dir,
            "--model-manifest",
            c.model_manifest,
            "--execute",
        ]
        return "cd " + shlex.quote(c.workdir) + " && " + " ".join(map(shlex.quote, args))

    def submit(self, task: Task, *, execute: bool = False) -> dict:
        """Default is a plan. An operator must separately authorize remote staging/run."""
        command = self.command(task)
        if not execute:
            return {"status": "PLAN_ONLY", "task_id": task.task_id, "command": command}
        path = str(PurePosixPath(self.config.workdir) / "inbox" / (task.task_id + ".json"))
        # Inbox and source deployment must already be approved/provisioned. No mkdir/install here.
        with self.client.open_sftp() as sftp:
            try:
                with sftp.open(path, "rb") as stream:
                    if stream.read(4 * 1024**2) != canonical(task.to_dict()):
                        raise ValueError("Conflicting remote task")
                return {"status": "EXISTS_POLL_ONLY", "task_id": task.task_id}
            except FileNotFoundError:
                pass
            with sftp.open(path, "wx") as stream:
                stream.write(canonical(task.to_dict()))
        deadline = time.monotonic() + 900
        try:
            _, out, _ = self.client.exec_command(command, timeout=900)
            return _collect_reply(out.channel, task.task_id, deadline)
        except (TimeoutError, OSError, EOFError):
            # Dispatch may already have reached the server; never submit a second time.
            return {
                "status": "SUBMITTED_OR_UNKNOWN",
                "task_id": task.task_id,
                "reason": "SSH_TRANSPORT_INTERRUPTED_POLL_ONLY",
                "automatic_retry": False,
            }

    def retrieve(self, task: Task) -> tuple[bytes, str]:
        path = str(PurePosixPath(self.config.workdir) / "jobs" / task.task_id / "result.json")
        with self.client.open_sftp() as sftp:
            with sftp.open(path, "rb") as stream:
                raw = stream.read(4 * 1024**2 + 1)
        if len(raw) > 4 * 1024**2:
            raise ValueError("Oversized remote result")
        # SSH integrity + content digest verified again by Windows Controller.accept.
        json.loads(raw)
        return raw, digest(raw)
