"""Tests for the 1Password CLI secret provider.

The real `op` binary needs an interactive 1Password session, so the subprocess
is stubbed here. What is under test is our own logic: how the command is built,
how output is trimmed, and what happens on every failure path.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.secrets.op_cli import OpCliError, OpCliProvider


class FakeProc:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang=False):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self):
        if self._hang:
            await asyncio.sleep(10)
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


@pytest.fixture
def spawn(monkeypatch):
    """Capture the argv the provider would exec, and control the fake result."""
    captured = {}

    def install(proc: FakeProc):
        async def fake_exec(*args, **kwargs):
            captured["argv"] = args
            return proc

        monkeypatch.setattr("backend.secrets.op_cli.shutil.which", lambda _: "/usr/bin/op")
        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        return captured

    return install


async def test_resolve_returns_secret(spawn):
    captured = spawn(FakeProc(stdout=b"hunter2"))
    provider = OpCliProvider()

    value = await provider.resolve("op://vault/item/credential")

    assert value == "hunter2"
    # --no-newline is required: without it op appends a trailing newline that
    # would have to be trimmed heuristically. The reference is also one argv
    # entry, never interpolated into a shell.
    assert captured["argv"] == (
        "op",
        "read",
        "--no-newline",
        "op://vault/item/credential",
    )


async def test_output_is_returned_verbatim(spawn):
    spawn(FakeProc(stdout=b"line1\nline2\n"))
    value = await OpCliProvider().resolve("op://vault/item/credential")
    # --no-newline means stdout is exactly the secret, so nothing is trimmed.
    assert value == "line1\nline2\n"


async def test_output_without_newline_is_untouched(spawn):
    spawn(FakeProc(stdout=b"nonewline"))
    assert await OpCliProvider().resolve("op://v/i/f") == "nonewline"


async def test_rejects_non_op_reference(spawn):
    spawn(FakeProc(stdout=b"x\n"))
    with pytest.raises(OpCliError, match="not a 1Password secret reference"):
        await OpCliProvider().resolve("https://example.com/secret")


async def test_rejects_reference_with_newline(spawn):
    spawn(FakeProc(stdout=b"x\n"))
    with pytest.raises(OpCliError, match="illegal characters"):
        await OpCliProvider().resolve("op://vault/item/cred\nrm -rf /")


async def test_missing_binary_gives_actionable_error(monkeypatch):
    monkeypatch.setattr("backend.secrets.op_cli.shutil.which", lambda _: None)
    with pytest.raises(OpCliError) as exc:
        await OpCliProvider().resolve("op://vault/item/credential")
    message = str(exc.value)
    assert "not on PATH" in message
    # The error should tell the reader how to fix it, not just that it broke.
    assert "developer.1password.com" in message
    assert "AGENTGATE_MODE=demo" in message


async def test_failure_surfaces_stderr_but_never_stdout(spawn):
    """A non-zero exit must not leak partial secret material into the error."""
    spawn(
        FakeProc(
            stdout=b"partial-secret-material",
            stderr=b"[ERROR] you are not currently signed in",
            returncode=1,
        )
    )
    with pytest.raises(OpCliError) as exc:
        await OpCliProvider().resolve("op://vault/item/credential")

    message = str(exc.value)
    assert "not currently signed in" in message
    assert "partial-secret-material" not in message


async def test_timeout_kills_the_process(spawn):
    proc = FakeProc(hang=True)
    spawn(proc)
    with pytest.raises(OpCliError, match="timed out"):
        await OpCliProvider(timeout=0.05).resolve("op://vault/item/credential")
    assert proc.killed, "a hung op process must be killed, not leaked"


async def test_ssh_key_uses_openssh_format(spawn):
    captured = spawn(FakeProc(stdout=b"-----BEGIN OPENSSH PRIVATE KEY-----\n"))
    await OpCliProvider().resolve_ssh_key("deploy-key")
    # Query-parameter form taken from `op read --help` on CLI 2.34.1.
    assert captured["argv"][3] == "op://SSH Keys/deploy-key/private key?ssh-format=openssh"


def test_factory_selects_cli_provider(monkeypatch):
    from backend.config import settings
    from backend.secrets.factory import create_secret_provider

    monkeypatch.setattr(settings, "mode", "cli")
    assert isinstance(create_secret_provider(), OpCliProvider)
