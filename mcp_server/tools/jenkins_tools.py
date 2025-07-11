from typing import Any, Dict, List

from ..base import ParameterSpec
from ..jenkins.jenkins_client import JenkinsClient
from .base_tools import JenkinsOperationTool


class GetJobParametersTool(JenkinsOperationTool):
    """Fetches Jenkins job parameters"""

    def __init__(self, jenkins_client: JenkinsClient, multi_jenkins_manager=None):
        super().__init__(
            jenkins_client=jenkins_client, multi_jenkins_manager=multi_jenkins_manager
        )

    @property
    def name(self) -> str:
        return "get_jenkins_job_parameters"

    @property
    def description(self) -> str:
        return "Fetches the defined parameters (name, type, description, default value) for a Jenkins job. IMPORTANT: jenkins_url is required because jobs are load-balanced across multiple Jenkins servers."

    @property
    def parameters(self) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                "job_name",
                str,
                "The full name of the Jenkins job (e.g., 'folder/my-pipeline')",
                required=True,
            ),
            ParameterSpec(
                "jenkins_url",
                str,
                "Jenkins instance URL (e.g., 'https://jenkins.example.com'). REQUIRED - jobs are load-balanced across multiple servers.",
                required=True,
            ),
        ]

    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        job_name = kwargs["job_name"]
        jenkins_url = kwargs["jenkins_url"]

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

        parameters = jenkins_client.get_job_parameters(job_name)

        return {
            "job_name": job_name,
            "parameters_count": len(parameters),
            "parameters": parameters,
        }
