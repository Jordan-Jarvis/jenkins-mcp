"""Specialized base classes for different tool categories"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional

from ..base import Build, ParameterSpec, Tool


class JenkinsOperationTool(Tool[Dict[str, Any]]):
    """Base class for tools that operate on Jenkins"""

    def __init__(self, jenkins_client=None, multi_jenkins_manager=None):
        # Support both legacy single-client and new multi-instance modes
        self.jenkins_client = jenkins_client
        self.multi_jenkins_manager = multi_jenkins_manager
        super().__init__()

    def get_jenkins_client(self, instance_id: Optional[str] = None):
        """Get Jenkins client for the specified instance"""
        if self.multi_jenkins_manager:
            return self.multi_jenkins_manager.get_jenkins_client(instance_id)
        else:
            # Legacy single-client mode
            return self.jenkins_client

    def resolve_jenkins_instance(
        self, jenkins_url: Optional[str] = None
    ) -> Optional[str]:
        """Resolve a Jenkins URL to an instance ID"""
        if not jenkins_url or not self.multi_jenkins_manager:
            return None

        try:
            return self.multi_jenkins_manager.resolve_jenkins_url(jenkins_url)
        except Exception as e:
            # Let the error bubble up with helpful context
            raise e

    def get_instance_instructions(self) -> str:
        """Get instructions for specifying Jenkins instances"""
        if self.multi_jenkins_manager:
            return self.multi_jenkins_manager.get_usage_instructions()
        else:
            return "Single Jenkins instance mode - no instance selection needed."

    @property
    def common_jenkins_parameters(self) -> List[ParameterSpec]:
        """Common parameters for Jenkins operations"""
        return [
            ParameterSpec("job_name", str, "Name of the Jenkins job", required=True),
            ParameterSpec("build_number", int, "Build number", required=True),
        ]


class LogOperationTool(Tool[Dict[str, Any]]):
    """Base class for tools that operate on logs"""

    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        super().__init__()


class VectorOperationTool(Tool[List[Dict[str, Any]]]):
    """Base class for tools that use vector operations"""

    def __init__(self, vector_manager):
        self.vector_manager = vector_manager
        super().__init__()
