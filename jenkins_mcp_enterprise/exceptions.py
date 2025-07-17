"""Custom exceptions for Jenkins MCP Server

This module provides domain-specific exceptions that replace silent failures
throughout the codebase, enabling proper error handling and debugging.

Each exception class is designed for specific failure scenarios and provides
meaningful error messages that help with debugging and error recovery.
"""


class JenkinsMCPError(Exception):
    """Base exception for all Jenkins MCP Server errors

    All custom exceptions in the Jenkins MCP Server inherit from this base
    class, allowing for consistent error handling and logging.
    """

    pass


class JenkinsConnectionError(JenkinsMCPError):
    """Raised when Jenkins connection fails

    This includes network errors, authentication failures, and Jenkins
    server unavailability. Used to distinguish transient connection
    issues from permanent configuration problems.
    """

    pass


class JenkinsAuthenticationError(JenkinsMCPError):
    """Raised when Jenkins authentication fails

    Specifically for authentication and authorization failures,
    separate from general connection errors.
    """

    pass


class BuildNotFoundError(JenkinsMCPError):
    """Raised when a Jenkins build cannot be found

    Used when requesting information about a build that doesn't exist
    or has been deleted from Jenkins.
    """

    pass


class CacheError(JenkinsMCPError):
    """Raised when cache operations fail

    Includes file system errors, cache corruption, and cache access issues.
    """

    pass


class VectorStoreError(JenkinsMCPError):
    """Raised when vector store operations fail

    Includes Pinecone connection errors, indexing failures, and
    search query errors.
    """

    pass


class ConfigurationError(JenkinsMCPError):
    """Raised when configuration is invalid

    Used for missing required configuration, invalid values,
    and configuration validation failures.
    """

    pass


class ToolExecutionError(JenkinsMCPError):
    """Raised when tool execution fails

    Used for tool-specific errors that don't fit into other categories.
    """

    pass


class LogProcessingError(JenkinsMCPError):
    """Raised when log processing operations fail

    Includes log fetching errors, parsing failures, and log file corruption.
    """

    pass


class SubBuildDiscoveryError(JenkinsMCPError):
    """Raised when sub-build discovery fails

    Used when unable to traverse pipeline hierarchies or discover
    nested builds.
    """

    pass


class CleanupError(JenkinsMCPError):
    """Raised when cleanup operations fail

    Used for file system cleanup failures and resource cleanup issues.
    Note: May be logged but not re-raised to allow cleanup to continue.
    """

    pass
