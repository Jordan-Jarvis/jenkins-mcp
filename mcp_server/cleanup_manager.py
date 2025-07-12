import os
import shutil
import time

from apscheduler.schedulers.background import BackgroundScheduler

from .config import CleanupConfig
from .exceptions import CleanupError
from .logging_config import get_component_logger

# Get logger for this component
logger = get_component_logger("cleanup_manager")


class CleanupManager:
    def __init__(self, config: CleanupConfig, cache_manager=None, vector_manager=None):
        """Initialize CleanupManager with configuration.

        Args:
            config: Cleanup configuration containing schedule and retention settings
            cache_manager: Cache manager for accessing cache directory
            vector_manager: Vector manager for Qdrant cleanup operations
        """
        self.config = config
        self.cache_manager = cache_manager
        self.vector_manager = vector_manager
        self.retention_seconds = (
            config.retention_days * 24 * 60 * 60
        )  # Convert days to seconds
        self.schedule_interval_hours = config.schedule_interval_hours
        self.max_concurrent_cleanups = config.max_concurrent_cleanups
        self.scheduler = None  # Initialize scheduler attribute

        logger.info(
            f"CleanupManager initialized with {config.retention_days} day retention"
        )

    def cleanup_expired_builds(self, cache_dir: str = None):
        """Clean up expired build data from cache directory.

        Args:
            cache_dir: Cache directory to clean. If not provided, will use a default.
        """
        # This method can be called with a cache_dir parameter for flexibility
        # In the future, this will be integrated with the cache manager
        target_cache_dir = cache_dir or "/tmp/mcp-jenkins"

        now = time.time()
        if not os.path.exists(target_cache_dir):
            logger.info(
                f"Cache directory {target_cache_dir} does not exist. Skipping cleanup."
            )
            return

        logger.info(f"Starting cleanup of expired builds in {target_cache_dir}")

        try:
            for job_name in os.listdir(target_cache_dir):
                job_path = os.path.join(target_cache_dir, job_name)
                if not os.path.isdir(job_path):
                    logger.debug(
                        f"Skipping non-directory item in cache_dir: {job_path}"
                    )
                    continue

                for build_id_or_name in os.listdir(
                    job_path
                ):  # Iterate through build-specific subdirectories
                    build_path = os.path.join(job_path, build_id_or_name)
                    if os.path.isdir(build_path):  # Ensure it's a directory
                        try:
                            dir_mtime = os.path.getmtime(
                                build_path
                            )  # Check mtime of the specific build_path
                            if (now - dir_mtime) > self.retention_seconds:
                                logger.info(
                                    f"Deleting expired cache directory: {build_path}"
                                )
                                shutil.rmtree(build_path)

                                # Clean up vector data for this build
                                if self.vector_manager and hasattr(
                                    self.vector_manager, "delete_build_data"
                                ):
                                    try:
                                        from .base import Build

                                        build_obj = Build(
                                            job_name=job_name,
                                            build_number=(
                                                int(build_id_or_name)
                                                if build_id_or_name.isdigit()
                                                else 0
                                            ),
                                            status="UNKNOWN",
                                            url="",
                                        )
                                        logger.info(
                                            f"Deleting vector data for {job_name}:{build_id_or_name}"
                                        )
                                        self.vector_manager.delete_build_data(build_obj)
                                        logger.info(
                                            f"Successfully deleted vector data for {job_name}:{build_id_or_name}"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Failed to delete vector data for {job_name}:{build_id_or_name}: {e}"
                                        )
                                        # Don't re-raise for cleanup operations to allow other cleanup to continue
                            else:
                                logger.debug(
                                    f"Cache directory {build_path} is not expired. Skipping."
                                )
                        except FileNotFoundError:
                            logger.debug(
                                f"Cache directory {build_path} was already removed. Skipping."
                            )
                            # This is expected behavior, not an error
                        except Exception as e:
                            logger.error(
                                f"Error processing cache directory {build_path}: {e}"
                            )
                            # Continue with other cleanup operations
                    else:
                        logger.debug(
                            f"Skipping non-directory item in job_path '{job_path}': {build_path}"
                        )
        except Exception as e:
            logger.error(f"Failed to cleanup expired builds: {e}")
            # Log error but don't re-raise to allow other operations to continue

    def cleanup_orphaned_vector_data(self) -> None:
        """Clean up orphaned vector data from Qdrant"""
        if not self.vector_manager or not hasattr(self.vector_manager, "client"):
            logger.info("Vector manager not available, skipping vector cleanup")
            return

        if getattr(self.vector_manager, "vector_search_disabled", False):
            logger.info("Vector search is disabled, skipping vector cleanup")
            return

        try:
            cutoff_time = time.time() - self.retention_seconds

            # Get all points with old timestamps
            # Note: This is a simplified approach. In practice, you'd want to
            # store creation timestamps in the payload and filter by them

            # For now, we'll clean up based on build directories that no longer exist
            cache_builds = set()
            if self.cache_manager and self.cache_manager.cache_dir.exists():
                for build_dir in self.cache_manager.cache_dir.iterdir():
                    if build_dir.is_dir():
                        # Extract build info from directory name
                        try:
                            parts = build_dir.name.split("_")
                            if len(parts) >= 2:
                                job_name = "_".join(parts[:-1])
                                build_number = int(parts[-1])
                                cache_builds.add(f"{job_name}:{build_number}")
                        except (ValueError, IndexError):
                            continue

            # Get all unique build_ids from Qdrant
            # This is a simplified approach - in production you'd want pagination
            if hasattr(self.vector_manager, "client") and self.vector_manager.client:
                search_results = self.vector_manager.client.scroll(
                    collection_name=self.vector_manager.collection_name,
                    limit=1000,  # Adjust based on your needs
                    with_payload=["build_id"],
                )

                qdrant_builds = set()
                for point in search_results[0]:
                    if "build_id" in point.payload:
                        qdrant_builds.add(point.payload["build_id"])

                # Delete vector data for builds that no longer have cache directories
                orphaned_builds = qdrant_builds - cache_builds

                for build_id in orphaned_builds:
                    try:
                        from qdrant_client.models import (
                            FieldCondition,
                            Filter,
                            MatchValue,
                        )

                        self.vector_manager.client.delete(
                            collection_name=self.vector_manager.collection_name,
                            points_selector=Filter(
                                must=[
                                    FieldCondition(
                                        key="build_id", match=MatchValue(value=build_id)
                                    )
                                ]
                            ),
                        )
                        logger.info(f"Cleaned up orphaned vector data for {build_id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to clean up vector data for {build_id}: {e}"
                        )

                logger.info(
                    f"Vector cleanup completed. Removed {len(orphaned_builds)} orphaned build datasets"
                )

        except Exception as e:
            logger.error(f"Vector cleanup failed: {e}")

    def schedule(self):
        """Start the cleanup scheduler with configured interval."""
        # Check if the scheduler is already running to prevent multiple instances if called multiple times
        if self.scheduler and self.scheduler.running:
            logger.info("Scheduler is already running.")
            return

        self.scheduler = BackgroundScheduler(
            daemon=True
        )  # daemon=True allows main program to exit even if job is scheduled

        # Schedule cache cleanup
        self.scheduler.add_job(
            self.cleanup_expired_builds, "interval", hours=self.schedule_interval_hours
        )

        # Schedule vector cleanup
        self.scheduler.add_job(
            self.cleanup_orphaned_vector_data,
            "interval",
            hours=self.schedule_interval_hours,
        )

        try:
            self.scheduler.start()
            logger.info(
                f"Cleanup scheduler started. Cache and vector cleanup will run every {self.schedule_interval_hours} hours."
            )
        except (KeyboardInterrupt, SystemExit):
            logger.info("Cleanup scheduler stopped.")
            self.scheduler.shutdown()
        except Exception as e:
            logger.error(f"Critical error starting cleanup scheduler: {e}")
            raise CleanupError(f"Failed to start cleanup scheduler: {e}") from e
