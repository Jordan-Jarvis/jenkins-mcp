"""Retry utilities for handling transient failures

This module provides decorators and utilities for retrying operations
that may fail due to transient issues like network connectivity problems.
"""

import random
import time
from functools import wraps
from typing import Any, Callable, Tuple, Type, Union

from .exceptions import JenkinsConnectionError, VectorStoreError
from .logging_config import get_component_logger

logger = get_component_logger("retry_utils")


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (JenkinsConnectionError,),
):
    """Decorator to retry function calls on transient failures

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_exceptions: Tuple of exception types that should trigger retries

    Returns:
        Decorated function that will retry on specified exceptions
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if this exception type should trigger a retry
                    if not isinstance(e, retry_exceptions):
                        logger.debug(
                            f"Exception {type(e).__name__} not in retry list, re-raising"
                        )
                        raise

                    # Don't sleep on the last attempt
                    if attempt < max_attempts - 1:
                        # Calculate delay with optional jitter
                        actual_delay = current_delay
                        if jitter:
                            # Add random jitter (±25% of the delay)
                            jitter_amount = current_delay * 0.25
                            actual_delay += random.uniform(
                                -jitter_amount, jitter_amount
                            )

                        # Ensure delay is never negative
                        actual_delay = max(0, actual_delay)

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {actual_delay:.2f}s"
                        )
                        time.sleep(actual_delay)

                        # Exponential backoff for next attempt
                        current_delay *= backoff_multiplier
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}. "
                            f"Final error: {e}"
                        )

            # Re-raise the last exception if all attempts failed
            raise last_exception

        return wrapper

    return decorator


def retry_jenkins_operation(max_attempts: int = 3, delay: float = 2.0):
    """Decorator specifically for Jenkins operations with appropriate defaults

    This is a convenience decorator for Jenkins operations that may fail
    due to network issues or temporary Jenkins unavailability.
    """
    return retry_on_failure(
        max_attempts=max_attempts,
        delay=delay,
        backoff_multiplier=1.5,
        jitter=True,
        retry_exceptions=(JenkinsConnectionError,),
    )


def retry_vector_operation(max_attempts: int = 2, delay: float = 1.0):
    """Decorator specifically for vector store operations

    Vector operations typically fail faster and may not benefit from
    as many retry attempts.
    """
    return retry_on_failure(
        max_attempts=max_attempts,
        delay=delay,
        backoff_multiplier=2.0,
        jitter=True,
        retry_exceptions=(VectorStoreError,),
    )


class RetryableOperation:
    """Context manager for retryable operations

    This provides an alternative to decorators for operations that need
    more complex retry logic or when decorating is not practical.

    Example:
        with RetryableOperation(max_attempts=3) as retry:
            result = retry.execute(lambda: some_operation())
    """

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        retry_exceptions: Tuple[Type[Exception], ...] = (JenkinsConnectionError,),
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_multiplier = backoff_multiplier
        self.retry_exceptions = retry_exceptions
        self.logger = get_component_logger("retry_operation")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, operation: Callable[[], Any]) -> Any:
        """Execute an operation with retry logic

        Args:
            operation: Callable that performs the operation

        Returns:
            Result of the operation

        Raises:
            Exception: The last exception if all retries fail
        """
        last_exception = None
        current_delay = self.delay

        for attempt in range(self.max_attempts):
            try:
                return operation()
            except Exception as e:
                last_exception = e

                if not isinstance(e, self.retry_exceptions):
                    self.logger.debug(f"Exception {type(e).__name__} not retryable")
                    raise

                if attempt < self.max_attempts - 1:
                    # Ensure delay is never negative
                    safe_delay = max(0, current_delay)
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {safe_delay:.2f}s"
                    )
                    time.sleep(safe_delay)
                    current_delay *= self.backoff_multiplier
                else:
                    self.logger.error(f"All {self.max_attempts} attempts failed")

        raise last_exception
