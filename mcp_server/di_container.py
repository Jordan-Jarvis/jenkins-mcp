"""Explicit dependency injection container for Jenkins MCP Server

This module provides a clean, type-safe dependency injection container
that replaces the problematic reflection-based dependency injection.

Key Features:
- Explicit dependency management with type safety
- Singleton behavior for all managed instances
- Clear initialization order and error handling
- No global state during module import
"""

from typing import Any, Dict, Optional, Type, TypeVar

from .cache_manager import CacheManager
from .cleanup_manager import CleanupManager
from .config import MCPConfig
from .config_factory import ConfigFactory
from .jenkins.jenkins_client import JenkinsClient
from .multi_jenkins_manager import MultiJenkinsManager
from .vector_manager import VectorManager

T = TypeVar("T")


class DIContainer:
    """Dependency injection container for managing singleton instances.

    This container manages the lifecycle of all core system components,
    ensuring they are initialized in the correct order and dependencies
    are satisfied.
    """

    def __init__(
        self, config: Optional[MCPConfig] = None, config_file_path: Optional[str] = None
    ) -> None:
        """Initialize the container and setup all managed dependencies.

        Args:
            config: Optional configuration instance. If not provided, will be loaded
                   using ConfigFactory with default behavior (environment variables).
            config_file_path: Optional path to config file for MultiJenkinsManager.
                            If provided, this will be passed to MultiJenkinsManager.
        """
        self._instances: Dict[Type[Any], Any] = {}
        self.config = config or ConfigFactory.create_config(
            config_file=config_file_path
        )
        self.config_file_path = config_file_path
        self._setup_managers()

    def _setup_managers(self) -> None:
        """Initialize all managers in the correct dependency order.

        Order matters:
        1. MultiJenkinsManager (manages multiple Jenkins instances)
        2. JenkinsClient (legacy single instance, now uses MultiJenkinsManager fallback)
        3. CacheManager (depends on CacheConfig)
        4. VectorManager (depends on VectorConfig, CacheManager, and JenkinsClient)
        5. CleanupManager (depends on CleanupConfig)
        """
        # Initialize multi-Jenkins manager first
        multi_jenkins_manager = MultiJenkinsManager(config_file=self.config_file_path)

        # Initialize legacy single Jenkins client via multi-Jenkins manager
        # This maintains backward compatibility
        jenkins_client = multi_jenkins_manager.get_jenkins_client()

        # Initialize managers with dependencies
        vector_manager = VectorManager(
            config=self.config.vector,
            cache_manager=None,  # Will be set after cache manager creation
            jenkins_client=jenkins_client,
        )

        # Initialize cache manager with vector manager for auto-indexing
        cache_manager = CacheManager(self.config.cache, vector_manager)
        cleanup_manager = CleanupManager(self.config.cleanup)

        # Set the cache manager reference in vector manager
        vector_manager.cache_manager = cache_manager

        # Register all instances
        self._instances[MultiJenkinsManager] = multi_jenkins_manager

        # Set the global instance
        from .multi_jenkins_manager import set_multi_jenkins_manager

        set_multi_jenkins_manager(multi_jenkins_manager)
        self._instances[JenkinsClient] = jenkins_client
        self._instances[CacheManager] = cache_manager
        self._instances[VectorManager] = vector_manager
        self._instances[CleanupManager] = cleanup_manager
        self._instances[MCPConfig] = self.config

    def get(self, dependency_type: Type[T]) -> T:
        """Get a managed dependency instance.

        Args:
            dependency_type: The type of dependency to retrieve

        Returns:
            The singleton instance of the requested type

        Raises:
            ValueError: If the dependency type is not registered
        """
        if dependency_type not in self._instances:
            raise ValueError(
                f"Dependency {dependency_type.__name__} is not registered. "
                f"Available types: {list(self._instances.keys())}"
            )

        return self._instances[dependency_type]

    def get_jenkins_client(self) -> JenkinsClient:
        """Convenience method to get JenkinsClient instance."""
        return self.get(JenkinsClient)

    def get_cache_manager(self) -> CacheManager:
        """Convenience method to get CacheManager instance."""
        return self.get(CacheManager)

    def get_vector_manager(self) -> VectorManager:
        """Convenience method to get VectorManager instance."""
        return self.get(VectorManager)

    def get_cleanup_manager(self) -> CleanupManager:
        """Convenience method to get CleanupManager instance."""
        return self.get(CleanupManager)

    def get_multi_jenkins_manager(self) -> MultiJenkinsManager:
        """Convenience method to get MultiJenkinsManager instance."""
        return self.get(MultiJenkinsManager)

    def get_config(self) -> MCPConfig:
        """Convenience method to get MCPConfig instance."""
        return self.get(MCPConfig)

    def start_cleanup_scheduler(self) -> None:
        """Start the cleanup manager's scheduled tasks.

        This should be called after the container is fully initialized
        and ready to begin background operations.
        """
        cleanup_manager = self.get_cleanup_manager()
        cleanup_manager.schedule()
