"""Network security guard module for sandbox isolation."""

import socket
import sys
import os
import logging
from typing import Any, Callable, Optional

# Logger
logger = logging.getLogger("ia-global")

class NetworkAccessBlocked(PermissionError):
    """Exception raised when script attempts network access."""
    pass

def _bloquear_conexao_origem(*args, **kwargs):
    """Universal interceptor that aborts socket connection attempts."""
    raise NetworkAccessBlocked(
        "SecurityError: Network access blocked. Sandbox has no permission for external connections."
    )

def blindar_rede_sandbox():
    """
    Replace native Python connection methods with security locks.
    Any socket.connect, socket.bind or socket.sendto will raise an error.
    """
    # 1. Low-level socket interception
    socket.socket.connect = _bloquear_conexao_origem
    socket.socket.connect_ex = _bloquear_conexao_origem
    socket.socket.bind = _bloquear_conexao_origem
    socket.socket.sendto = _bloquear_conexao_origem
    
    # 2. DNS name resolution interception
    socket.getaddrinfo = _bloquear_conexao_origem
    socket.gethostbyname = _bloquear_conexao_origem
    socket.gethostbyname_ex = _bloquear_conexao_origem
    socket.getnameinfo = _bloquear_conexao_origem
    
    # 3. Remove proxy environment variables
    for env_var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        if env_var in os.environ:
            del os.environ[env_var]

class NetworkGuard:
    """Guard class for network access control in sandbox."""
    
    def __init__(self, allow_network: bool = False):
        self.allow_network = allow_network
        self.blocked_hosts = set()
        self.blocked_ports = set()
        self.allowed_hosts = set()
        self.original_socket_create = socket.socket
    
    def enable_isolation(self) -> None:
        """Enable strict network isolation."""
        if not self.allow_network:
            blindar_rede_sandbox()
            logger.info("Network isolation enabled")
    
    def disable_isolation(self) -> None:
        """Disable network isolation (not recommended)."""
        # Restore original socket
        socket.socket = self.original_socket_create
        logger.warning("Network isolation disabled - UNSAFE MODE")
    
    def block_host(self, hostname: str) -> None:
        """Block access to specific host."""
        self.blocked_hosts.add(hostname)
    
    def block_port(self, port: int) -> None:
        """Block access to specific port."""
        self.blocked_ports.add(port)
    
    def allow_host(self, hostname: str) -> None:
        """Allow access to specific host (whitelist)."""
        self.allowed_hosts.add(hostname)
    
    def is_host_blocked(self, hostname: str) -> bool:
        """Check if host is blocked."""
        return hostname in self.blocked_hosts
    
    def is_port_blocked(self, port: int) -> bool:
        """Check if port is blocked."""
        return port in self.blocked_ports
    
    def get_blocked_hosts(self) -> set:
        """Get set of blocked hosts."""
        return self.blocked_hosts.copy()
    
    def get_blocked_ports(self) -> set:
        """Get set of blocked ports."""
        return self.blocked_ports.copy()
    
    def get_allowed_hosts(self) -> set:
        """Get set of allowed hosts."""
        return self.allowed_hosts.copy()
    
    def reset_blocks(self) -> None:
        """Reset all blocking rules."""
        self.blocked_hosts.clear()
        self.blocked_ports.clear()
    
    def test_isolation(self) -> bool:
        """Test if isolation is working."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 80))
            return False  # Should not reach here
        except NetworkAccessBlocked:
            return True  # Isolation working
        except Exception as e:
            logger.error(f"Unexpected error during isolation test: {e}")
            return False

if __name__ == "__main__":
    try:
        blindar_rede_sandbox()
        print("Network Guard loaded successfully. Testing block...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 80))
    except NetworkAccessBlocked as e:
        print(f"Success: Blocker intercepted connection! Report: {e}")
    except Exception as e:
        print(f"Unexpected error during module test: {e}")
