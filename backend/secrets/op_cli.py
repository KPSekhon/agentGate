from __future__ import annotations

import asyncio
import shutil

_OP_SCHEME = "op://"


class OpCliError(RuntimeError):
    """Raised when the 1Password CLI cannot resolve a reference."""


class OpCliProvider:
    """Resolve secrets by shelling out to the 1Password CLI (``op``).

    This is the local-development counterpart to :class:`OnePasswordProvider`.
    The SDK path needs a service account token, which is a provisioning step and
    cannot reach a developer's personal vaults. The CLI instead reuses the
    session the developer already has from the 1Password desktop app, including
    biometric unlock, so nothing has to be minted or exported to run the broker
    against real secrets on a laptop.

    Servers and CI should still use the SDK: service accounts are auditable and
    non-interactive, whereas the CLI depends on a human session.

    Requires 1Password CLI 2.x (verified against 2.34.1) for the
    ``read --no-newline`` flag.
    """

    def __init__(self, op_path: str = "op", timeout: float = 30.0) -> None:
        self._op = op_path
        self._timeout = timeout

    async def resolve(self, secret_ref: str) -> str:
        if not secret_ref.startswith(_OP_SCHEME):
            raise OpCliError(f"not a 1Password secret reference: {secret_ref!r}")
        return await self._read(secret_ref)

    async def resolve_ssh_key(self, key_name: str) -> str:
        ref = f"op://SSH Keys/{key_name}/private key?ssh-format=openssh"
        return await self._read(ref)

    async def _read(self, ref: str) -> str:
        if "\n" in ref or "\x00" in ref:
            raise OpCliError("secret reference contains illegal characters")

        if shutil.which(self._op) is None:
            raise OpCliError(
                f"the 1Password CLI ({self._op!r}) is not on PATH. Install it from "
                "https://developer.1password.com/docs/cli/get-started/ or set "
                "AGENTGATE_MODE=demo to run without it."
            )

        # exec form, never a shell: the reference is passed as a single argv
        # entry so nothing in it can be interpreted as shell syntax.
        proc = await asyncio.create_subprocess_exec(
            self._op,
            "read",
            # Without this op appends a trailing newline, which would otherwise
            # have to be stripped heuristically. Asking op not to add one is
            # exact: a secret that genuinely ends in a newline keeps it.
            "--no-newline",
            ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise OpCliError(
                f"`op read` timed out after {self._timeout}s. If the vault is "
                "locked, unlock 1Password and retry."
            ) from None

        if proc.returncode != 0:
            # Surface stderr only. stdout may hold partial secret material and
            # must never reach a log line or an API response.
            detail = stderr.decode(errors="replace").strip() or "no error output"
            raise OpCliError(f"`op read` failed ({proc.returncode}): {detail}")

        # Returned verbatim: --no-newline means stdout is exactly the secret,
        # so there is nothing to trim and a secret that genuinely ends in a
        # newline survives intact.
        return stdout.decode()
