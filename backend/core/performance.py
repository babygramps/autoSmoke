"""Performance monitoring and logging utilities."""

import time
import logging
from typing import Optional, Callable
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    def __init__(self):
        self.metrics = {}
    
    @contextmanager
    def measure(self, operation_name: str, log_slow_threshold_ms: float = 100.0):
        """
        Context manager to measure operation time.
        
        Args:
            operation_name: Name of the operation being measured
            log_slow_threshold_ms: Log a warning if operation exceeds this threshold
            
        Example:
            with perf_monitor.measure("database_query"):
                result = session.exec(query).all()
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # Store metric
            if operation_name not in self.metrics:
                self.metrics[operation_name] = {
                    'count': 0,
                    'total_ms': 0.0,
                    'min_ms': float('inf'),
                    'max_ms': 0.0
                }
            
            metric = self.metrics[operation_name]
            metric['count'] += 1
            metric['total_ms'] += duration_ms
            metric['min_ms'] = min(metric['min_ms'], duration_ms)
            metric['max_ms'] = max(metric['max_ms'], duration_ms)
            
            # Log if slow
            if duration_ms > log_slow_threshold_ms:
                avg_ms = metric['total_ms'] / metric['count']
                logger.warning(
                    f"⚠️  Slow operation: {operation_name} took {duration_ms:.1f}ms "
                    f"(avg: {avg_ms:.1f}ms, threshold: {log_slow_threshold_ms}ms)"
                )
            else:
                logger.debug(f"⏱️  {operation_name}: {duration_ms:.1f}ms")
    
    def measure_func(self, log_slow_threshold_ms: float = 100.0):
        """
        Decorator to measure function execution time.
        
        Args:
            log_slow_threshold_ms: Log a warning if function exceeds this threshold
            
        Example:
            @perf_monitor.measure_func(log_slow_threshold_ms=200)
            def expensive_function():
                pass
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                operation_name = f"{func.__module__}.{func.__name__}"
                with self.measure(operation_name, log_slow_threshold_ms):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_metrics(self) -> dict:
        """Get all collected metrics."""
        result = {}
        for operation_name, metric in self.metrics.items():
            avg_ms = metric['total_ms'] / metric['count'] if metric['count'] > 0 else 0
            result[operation_name] = {
                'count': metric['count'],
                'avg_ms': round(avg_ms, 2),
                'min_ms': round(metric['min_ms'], 2),
                'max_ms': round(metric['max_ms'], 2),
                'total_ms': round(metric['total_ms'], 2)
            }
        return result
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        self.metrics = {}
        logger.info("Performance metrics reset")
    
    def log_summary(self):
        """Log a summary of all metrics."""
        if not self.metrics:
            logger.info("No performance metrics collected")
            return
        
        logger.info("=" * 60)
        logger.info("PERFORMANCE METRICS SUMMARY")
        logger.info("=" * 60)
        
        # Sort by total time
        sorted_metrics = sorted(
            self.metrics.items(),
            key=lambda x: x[1]['total_ms'],
            reverse=True
        )
        
        for operation_name, metric in sorted_metrics:
            avg_ms = metric['total_ms'] / metric['count']
            logger.info(
                f"{operation_name}:\n"
                f"  Count: {metric['count']}\n"
                f"  Avg: {avg_ms:.1f}ms\n"
                f"  Min: {metric['min_ms']:.1f}ms\n"
                f"  Max: {metric['max_ms']:.1f}ms\n"
                f"  Total: {metric['total_ms']:.1f}ms"
            )
        
        logger.info("=" * 60)


# Global performance monitor
perf_monitor = PerformanceMonitor()

