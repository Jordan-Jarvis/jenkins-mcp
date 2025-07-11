"""Core Jenkins connection and authentication management"""

from typing import Any, Dict, Optional

import jenkins
import requests

from ..config import JenkinsConfig
from ..exceptions import JenkinsAuthenticationError, JenkinsConnectionError
from ..logging_config import get_component_logger

logger = get_component_logger("jenkins.connection")


class JenkinsConnectionManager:
    """Manages Jenkins connection and authentication"""

    def __init__(self, config: JenkinsConfig):
        self.config = config
        self._client: Optional[jenkins.Jenkins] = None
        self._session: Optional[requests.Session] = None
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize Jenkins client and HTTP session"""
        try:
            self._client = jenkins.Jenkins(
                self.config.url,
                username=self.config.username,
                password=self.config.token,
            )

            # Test connection
            whoami = self._client.get_whoami()
            logger.info(f"Connected to Jenkins as: {whoami}")

        except Exception as e:
            raise JenkinsConnectionError(f"Failed to connect to Jenkins: {e}") from e

        # Setup HTTP session for Blue Ocean API
        self._session = requests.Session()
        if self.config.username and self.config.token:
            self._session.auth = (self.config.username, self.config.token)
        self._session.verify = self.config.verify_ssl

    @property
    def client(self) -> jenkins.Jenkins:
        """Get the Jenkins client"""
        if not self._client:
            raise JenkinsConnectionError("Jenkins client not initialized")
        return self._client

    @property
    def session(self) -> requests.Session:
        """Get the HTTP session for API calls"""
        if not self._session:
            raise JenkinsConnectionError("HTTP session not initialized")
        return self._session

    def test_connection(self) -> bool:
        """Test if the Jenkins connection is working"""
        try:
            self.client.get_whoami()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """Get Jenkins server information"""
        try:
            return self.client.get_info()
        except Exception as e:
            raise JenkinsConnectionError(f"Failed to get server info: {e}") from e

    def authenticate(self) -> bool:
        """Test authentication explicitly"""
        try:
            whoami = self.client.get_whoami()
            if whoami:
                logger.info(
                    f"Authentication successful for user: {whoami.get('fullName', 'unknown')}"
                )
                return True
            else:
                raise JenkinsAuthenticationError(
                    "Authentication failed: no user information returned"
                )
        except Exception as e:
            raise JenkinsAuthenticationError(f"Authentication failed: {e}") from e
