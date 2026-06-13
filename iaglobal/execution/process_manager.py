"""Process manager for handling subprocess execution."""

import subprocess
from typing import Tuple, Optional

class ProcessManager:
    """Manages external process execution."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.processes = {}
    
    def run(self, command: str, cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Process timeout"
        except Exception as e:
            return -1, "", str(e)
    
    def kill_process(self, pid: int) -> bool:
        """Kill a process by PID."""
        try:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)
            return True
        except:
            return False
