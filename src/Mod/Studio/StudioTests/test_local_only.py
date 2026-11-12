# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio is local-only: no network access unless the user explicitly asks for it."""

import importlib
import pkgutil
import socket
import sys
import unittest

from StudioTests.support import NetworkAccessError, no_network


class NoNetworkGuardTest(unittest.TestCase):
    """The guard must actually block, or tests that rely on it prove nothing."""

    def test_blocks_outbound_connection(self):
        with no_network():
            with self.assertRaises(NetworkAccessError):
                socket.create_connection(("127.0.0.1", 9), timeout=0.1)

    def test_blocks_dns_lookup(self):
        with no_network():
            with self.assertRaises(NetworkAccessError):
                socket.getaddrinfo("example.com", 443)

    def test_restores_socket_functions_afterwards(self):
        before = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
        with no_network():
            pass
        after = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
        self.assertEqual(before, after)


class StudioIsLocalOnlyTest(unittest.TestCase):
    def test_importing_every_studio_module_makes_no_network_access(self):
        import studio

        names = [studio.__name__] + [
            info.name for info in pkgutil.walk_packages(studio.__path__, "studio.")
        ]
        with no_network():
            for name in names:
                with self.subTest(module=name):
                    sys.modules.pop(name, None)
                    importlib.import_module(name)
