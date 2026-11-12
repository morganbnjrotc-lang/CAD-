# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared test helpers for Studio suites."""

import contextlib
import socket


def preserve_param(testcase, group, kind: str, name: str) -> None:
    """Restore a FreeCAD parameter after the test, including "it did not exist".

    `group` is a ParamGet() handle, `kind` one of "String", "Bool", "Int", "Float", "Unsigned".
    """
    existed = any(entry[1] == name for entry in group.GetContents() or [])
    value = getattr(group, f"Get{kind}")(name) if existed else None

    def restore():
        if existed:
            getattr(group, f"Set{kind}")(name, value)
        else:
            getattr(group, f"Rem{kind}")(name)

    testcase.addCleanup(restore)


class NetworkAccessError(AssertionError):
    """Raised when code under test tries to reach the network inside `no_network()`."""


@contextlib.contextmanager
def no_network():
    """Fail any outbound connection or DNS lookup made inside the block.

    Studio is local-only (README principle 3): product code must not touch the network unless
    the user explicitly asks. Wrap code under test in this guard to prove it.
    """

    def refuse(*args, **kwargs):
        raise NetworkAccessError(f"network access attempted: {args[1:] or args}")

    patched = [
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket, "create_connection"),
        (socket, "getaddrinfo"),
    ]
    originals = [(owner, name, getattr(owner, name)) for owner, name in patched]
    try:
        for owner, name in patched:
            setattr(owner, name, refuse)
        yield
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)
