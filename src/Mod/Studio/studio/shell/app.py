# SPDX-License-Identifier: LGPL-2.1-or-later
"""Instances the whole shell shares during a session. Created on first use, not at startup:
loading the command catalog is work startup doesn't need."""

from studio.services.commands import CommandCatalog, CommandService
from studio.services.settings import Settings

_command_service = None


def command_service() -> CommandService:
    """The session's command service: one per session, so a workbench is loaded only once."""
    global _command_service
    if _command_service is None:
        from studio.shell.backend import FreeCADCommandBackend

        _command_service = CommandService(CommandCatalog.load(), FreeCADCommandBackend())
    return _command_service


def settings() -> Settings:
    return Settings()
