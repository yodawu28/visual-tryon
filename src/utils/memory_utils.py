"""
Memory management utilities cho ML models.
"""

import gc
import psutil
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Memory cleanup utilities.
    """

    @staticmethod
    def get_memory_usage() -> dict:
        """Get current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
            "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            "percent": process.memory_percent(),
        }

    @staticmethod
    def force_cleanup():
        """
        Force garbage collection và memory cleanup.
        Gọi sau khi xử lý image để giải phóng memory.
        """
        gc.collect()

        # Log memory after cleanup
        mem = MemoryManager.get_memory_usage()
        logger.info(
            f"Memory after cleanup: {mem['rss_mb']:.2f} MB ({mem['percent']:.1f}%)"
        )

    @staticmethod
    def cleanup_large_variables(*variables: Any):
        """
        Explicitly delete large variables và trigger GC.
        """
        for var in variables:
            try:
                del var
            except Exception:
                pass

        gc.collect()
