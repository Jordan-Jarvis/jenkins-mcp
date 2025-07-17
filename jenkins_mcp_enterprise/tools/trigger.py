"""Updated trigger tools with standardized interfaces"""

from typing import Any, Dict, List

from ..base import ParameterSpec
from ..cache_manager import CacheManager
from ..jenkins.jenkins_client import JenkinsClient
from .base_tools import JenkinsOperationTool
from .common import CommonParameters


class TriggerBuildTool(JenkinsOperationTool):
    """Triggers a Jenkins build and waits for completion"""

    def __init__(self, jenkins_client: JenkinsClient, multi_jenkins_manager=None):
        super().__init__(
            jenkins_client=jenkins_client, multi_jenkins_manager=multi_jenkins_manager
        )

    @property
    def name(self) -> str:
        return "trigger_build"

    @property
    def description(self) -> str:
        return "Triggers a Jenkins job, waits for it to complete, and returns its final status and identifiers. IMPORTANT: jenkins_url is required because jobs are load-balanced across multiple Jenkins servers."

    @property
    def parameters(self) -> List[ParameterSpec]:
        return [
            CommonParameters.job_name_param(),
            CommonParameters.jenkins_url_param(),
            ParameterSpec(
                "params", dict, "Build parameters", required=False, default={}
            ),
            ParameterSpec(
                "build_complete_poll_interval",
                float,
                "Polling interval in seconds",
                required=False,
                default=5.0,
            ),
            ParameterSpec(
                "build_complete_timeout",
                float,
                "Timeout in seconds",
                required=False,
                default=600.0,
            ),
        ]

    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        job_name = kwargs["job_name"]
        jenkins_url = kwargs["jenkins_url"]
        params = kwargs["params"]
        poll_interval = kwargs["build_complete_poll_interval"]
        timeout = kwargs["build_complete_timeout"]

        # Resolve Jenkins instance
        try:
            instance_id = self.resolve_jenkins_instance(jenkins_url)
            jenkins_client = self.get_jenkins_client(instance_id)
        except Exception as e:
            return {
                "job_name": job_name,
                "jenkins_url": jenkins_url,
                "error": f"Jenkins instance resolution failed: {str(e)}",
                "instructions": self.get_instance_instructions(),
            }

        # Trigger build
        build = jenkins_client.trigger_build(job_name, params)

        # Wait for completion
        completed_build = jenkins_client.wait_for_completion(
            job_name, build.build_number, poll_interval, timeout
        )

        return {
            "job_name": completed_build.job_name,
            "build_number": completed_build.build_number,
            "status": completed_build.status,
            "url": completed_build.url,
            "parameters": completed_build.parameters,
        }


class AsyncBuildTool(JenkinsOperationTool):
    """Triggers a Jenkins build asynchronously"""

    def __init__(
        self,
        jenkins_client: JenkinsClient,
        cache_manager: CacheManager,
        multi_jenkins_manager=None,
    ):
        super().__init__(
            jenkins_client=jenkins_client, multi_jenkins_manager=multi_jenkins_manager
        )
        self.cache_manager = cache_manager

    @property
    def name(self) -> str:
        return "trigger_build_async"

    @property
    def description(self) -> str:
        return "Starts a Jenkins job asynchronously and returns immediately with the build URL and cache path. IMPORTANT: jenkins_url is required because jobs are load-balanced across multiple Jenkins servers."

    @property
    def parameters(self) -> List[ParameterSpec]:
        return [
            CommonParameters.job_name_param(),
            CommonParameters.jenkins_url_param(),
            ParameterSpec(
                "params", dict, "Build parameters", required=False, default={}
            ),
        ]

    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        job_name = kwargs["job_name"]
        jenkins_url = kwargs["jenkins_url"]
        params = kwargs["params"]

        # Resolve Jenkins instance from required URL
        try:
            instance_id = self.resolve_jenkins_instance(jenkins_url)
            jenkins_client = self.get_jenkins_client(instance_id)
        except Exception as e:
            return {
                "job_name": job_name,
                "jenkins_url": jenkins_url,
                "error": f"Jenkins instance resolution failed: {str(e)}",
                "instructions": self.get_instance_instructions(),
            }

        build = jenkins_client.trigger_build(job_name, params)

        # Get cache path for the build
        cache_path = str(self.cache_manager.get_path(build))

        return {
            "job_name": build.job_name,
            "build_number": build.build_number,
            "status": build.status,
            "url": build.url,
            "parameters": build.parameters,
            "estimated_cache_path": cache_path,
        }
