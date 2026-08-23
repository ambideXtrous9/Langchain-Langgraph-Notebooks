"""Rate Limiting and Reliability Middleware for Error and Confidence Tracking."""

import logging
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple
from langchain_core.messages import BaseMessage
from app.middleware.base import AgentMiddleware

logger = logging.getLogger(__name__)


class RateLimitExceededException(Exception):
    """Raised when rate limit or consecutive error budget is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class RateLimitMiddleware(AgentMiddleware):
    """Enforces sliding-window rate limits, tracks error budgets, and evaluates confidence."""

    name: str = "rate_limiter"

    def __init__(
        self,
        max_requests_per_window: int = 60,
        window_seconds: int = 60,
        max_consecutive_errors: int = 3,
        min_confidence_threshold: float = 0.5,
    ):
        """
        Initializes RateLimitMiddleware.

        Args:
            max_requests_per_window: Maximum requests allowed per window.
            window_seconds: Sliding window duration in seconds.
            max_consecutive_errors: Max errors allowed before circuit breaking.
            min_confidence_threshold: Minimum expected classification / reasoning confidence.
        """
        self.max_requests = max_requests_per_window
        self.window_seconds = window_seconds
        self.max_errors = max_consecutive_errors
        self.min_confidence = min_confidence_threshold

        # In-memory tracking per key (thread_id / user_id)
        self._request_history: Dict[str, Deque[float]] = defaultdict(deque)
        self._error_counts: Dict[str, int] = defaultdict(int)

    def _get_key(self, state: Dict[str, Any]) -> str:
        """Extracts tracking key from state (user_id > thread_id > 'global')."""
        return str(state.get("user_id") or state.get("thread_id") or state.get("session_id") or "global")

    def check_rate_limit(self, key: str) -> None:
        """Enforces sliding window limit for the given key."""
        now = time.time()
        timestamps = self._request_history[key]

        # Evict timestamps older than the window
        while timestamps and timestamps[0] < now - self.window_seconds:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            logger.warning(f"Rate limit exceeded for key '{key}'. Retry after {retry_after}s.")
            raise RateLimitExceededException(
                f"Rate limit of {self.max_requests} requests per {self.window_seconds}s exceeded. Please try again in {retry_after}s.",
                retry_after=retry_after,
            )

        timestamps.append(now)

    def record_error(self, key: str) -> int:
        """Increments and returns consecutive error count for the key."""
        self._error_counts[key] += 1
        count = self._error_counts[key]
        if count >= self.max_errors:
            logger.error(f"Circuit tripped: {count} consecutive errors for key '{key}'.")
        return count

    def reset_error_count(self, key: str) -> None:
        """Resets consecutive error count upon a successful operation."""
        self._error_counts[key] = 0

    def get_error_count(self, key: str) -> int:
        """Returns current error count for key."""
        return self._error_counts.get(key, 0)

    async def before_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validates rate limit and error budget before agent begins."""
        key = self._get_key(state)
        self.check_rate_limit(key)

        current_errors = self._error_counts[key]
        if current_errors >= self.max_errors:
            logger.warning(f"Agent executing under elevated error count ({current_errors}/{self.max_errors}) for key '{key}'.")
            state["circuit_breaker_active"] = True

        return state

    async def after_model(
        self,
        state: Dict[str, Any],
        response: Any,
    ) -> Tuple[Dict[str, Any], Any]:
        """Evaluates confidence metric and resets error budget upon valid response."""
        key = self._get_key(state)

        # Check confidence if present in response or state
        confidence = state.get("confidence")
        if confidence is not None and isinstance(confidence, (int, float)):
            if confidence < self.min_confidence:
                logger.warning(f"Low confidence ({confidence:.2f} < {self.min_confidence:.2f}) observed for key '{key}'.")
                state["low_confidence_flag"] = True

        # Reset error count on successful model return
        self.reset_error_count(key)
        return state, response
