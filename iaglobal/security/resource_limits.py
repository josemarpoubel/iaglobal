"""Resource limits module for sandbox execution."""

import resource
import sys
from typing import Dict, Any, Tuple
from iaglobal.utils.logger import logger

# Resource limits for AI-generated code
MAX_MEMORIA_MB = 256  # Max 256MB RAM
MAX_CPU_SEGUNDOS = 5  # Max 5 seconds CPU time
MAX_ARQUIVO_BYTES = 1024 * 1024  # Max 1MB file size
MAX_PROCESSOS = 0  # No subprocess spawning

def limitar_recursos_sandbox():
    """
    Apply strict hardware restrictions at Linux Kernel level.
    Should be injected into subprocess preexec_fn parameter.
    """
    try:
        # 1. Limit virtual memory (RAM)
        limite_memoria_bytes = MAX_MEMORIA_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limite_memoria_bytes, limite_memoria_bytes))

        # 2. Limit CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SEGUNDOS, MAX_CPU_SEGUNDOS))

        # 3. Limit file size
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_ARQUIVO_BYTES, MAX_ARQUIVO_BYTES))

        # 4. Prevent subprocess spawning
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSOS, MAX_PROCESSOS))

    except Exception as e:
        sys.exit(f"Critical security error applying resource limits: {e}")

class ResourceLimiter:
    """Class for managing resource limits in sandbox."""
    
    def __init__(self, 
                 memory_mb: int = MAX_MEMORIA_MB,
                 cpu_seconds: int = MAX_CPU_SEGUNDOS,
                 file_bytes: int = MAX_ARQUIVO_BYTES,
                 max_processes: int = MAX_PROCESSOS):
        self.memory_mb = memory_mb
        self.cpu_seconds = cpu_seconds
        self.file_bytes = file_bytes
        self.max_processes = max_processes
        self.limits_applied = False
    
    def apply_limits(self) -> bool:
        """Apply resource limits to current process."""
        try:
            # Memory limit
            memory_bytes = self.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_seconds, self.cpu_seconds))
            
            # File size limit
            resource.setrlimit(resource.RLIMIT_FSIZE, (self.file_bytes, self.file_bytes))
            
            # Process limit
            resource.setrlimit(resource.RLIMIT_NPROC, (self.max_processes, self.max_processes))
            
            self.limits_applied = True
            logger.info(f"Resource limits applied: {self.memory_mb}MB RAM, {self.cpu_seconds}s CPU")
            return True
        except Exception as e:
            logger.error(f"Failed to apply resource limits: {e}")
            return False
    
    def get_current_limits(self) -> Dict[str, Tuple[int, int]]:
        """Get current resource limits."""
        try:
            return {
                'memory': resource.getrlimit(resource.RLIMIT_AS),
                'cpu': resource.getrlimit(resource.RLIMIT_CPU),
                'file_size': resource.getrlimit(resource.RLIMIT_FSIZE),
                'processes': resource.getrlimit(resource.RLIMIT_NPROC),
            }
        except Exception as e:
            logger.error(f"Error getting resource limits: {e}")
            return {}
    
    def get_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return {
                'user_time': usage.ru_utime,
                'system_time': usage.ru_stime,
                'max_rss': usage.ru_maxrss,
                'shared_memory': usage.ru_ixrss,
                'page_faults': usage.ru_majflt + usage.ru_minflt,
            }
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {}
    
    def set_memory_limit(self, mb: int) -> bool:
        """Set memory limit."""
        self.memory_mb = mb
        try:
            memory_bytes = mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            logger.info(f"Memory limit set to {mb}MB")
            return True
        except Exception as e:
            logger.error(f"Failed to set memory limit: {e}")
            return False
    
    def set_cpu_limit(self, seconds: int) -> bool:
        """Set CPU time limit."""
        self.cpu_seconds = seconds
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
            logger.info(f"CPU limit set to {seconds} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to set CPU limit: {e}")
            return False
    
    def set_file_limit(self, bytes_size: int) -> bool:
        """Set file size limit."""
        self.file_bytes = bytes_size
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (bytes_size, bytes_size))
            logger.info(f"File limit set to {bytes_size} bytes")
            return True
        except Exception as e:
            logger.error(f"Failed to set file limit: {e}")
            return False
    
    def is_limits_applied(self) -> bool:
        """Check if limits are applied."""
        return self.limits_applied
    
    def get_config(self) -> Dict[str, int]:
        """Get current configuration."""
        return {
            'memory_mb': self.memory_mb,
            'cpu_seconds': self.cpu_seconds,
            'file_bytes': self.file_bytes,
            'max_processes': self.max_processes,
        }
