"""
Retry utilities with exponential backoff for transient failures.

This module provides decorators and utilities for retrying operations
that may fail due to temporary issues (network, database, external services).
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None
):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry
        
    Example:
        @retry_with_backoff(max_attempts=3, base_delay=0.5)
        def flaky_function():
            # Code that might fail transiently
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as exc:
                    last_exception = exc
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            exc_info=True
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.2f}s: {exc}"
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(exc, attempt)
                    
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception  # type: ignore
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as exc:
                    last_exception = exc
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Async function {func.__name__} failed after {max_attempts} attempts",
                            exc_info=True
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )
                    
                    logger.warning(
                        f"Async function {func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.2f}s: {exc}"
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(exc, attempt)
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception  # type: ignore
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        return min(
            self.base_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )


# Predefined retry configurations for common scenarios
DATABASE_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    exponential_base=2.0
)

EXTERNAL_API_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0
)

BROWSER_RETRY = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    exponential_base=2.0
)


async def retry_async(
    func: Callable[..., T],
    *args,
    config: RetryConfig = DATABASE_RETRY,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs
) -> T:
    """
    Retry an async function with the given configuration.
    
    This is useful when you can't use the decorator (e.g., dynamic retry config).
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration
        exceptions: Tuple of exception types to catch and retry
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func
        
    Raises:
        Last exception if all retries fail
        
    Example:
        result = await retry_async(
            fetch_data,
            url="https://api.example.com",
            config=EXTERNAL_API_RETRY
        )
    """
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
            
        except exceptions as exc:
            last_exception = exc
            
            if attempt == config.max_attempts:
                logger.error(
                    f"Function {func.__name__} failed after {config.max_attempts} attempts",
                    exc_info=True
                )
                raise
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                f"retrying in {delay:.2f}s: {exc}"
            )
            
            await asyncio.sleep(delay)
    
    raise last_exception  # type: ignore


def retry_sync(
    func: Callable[..., T],
    *args,
    config: RetryConfig = DATABASE_RETRY,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs
) -> T:
    """
    Retry a sync function with the given configuration.
    
    Similar to retry_async but for synchronous functions.
    """
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return func(*args, **kwargs)
            
        except exceptions as exc:
            last_exception = exc
            
            if attempt == config.max_attempts:
                logger.error(
                    f"Function {func.__name__} failed after {config.max_attempts} attempts",
                    exc_info=True
                )
                raise
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                f"retrying in {delay:.2f}s: {exc}"
            )
            
            time.sleep(delay)
    
    raise last_exception  # type: ignore
