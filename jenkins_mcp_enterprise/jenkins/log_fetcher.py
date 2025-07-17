"""Jenkins console log fetching and processing"""

import time
from typing import List, Optional

import requests

from ..exceptions import JenkinsConnectionError
from ..logging_config import get_component_logger
from .connection_manager import JenkinsConnectionManager

logger = get_component_logger("jenkins.log")


class LogFetcher:
    """Handles fetching console logs from Jenkins"""

    def __init__(self, connection_manager: JenkinsConnectionManager):
        self.connection = connection_manager

    def get_console_log(
        self,
        job_name: str,
        build_number: int,
        start_line: int = 0,
        end_line: Optional[int] = None,
    ) -> List[str]:
        """Fetch console log lines for a build"""
        try:
            # Try progressive log API first
            if start_line > 0 or end_line is not None:
                return self._get_progressive_log(
                    job_name, build_number, start_line, end_line
                )
            else:
                return self._get_full_log(job_name, build_number)

        except Exception as e:
            raise JenkinsConnectionError(
                f"Failed to fetch log for {job_name}#{build_number}: {e}"
            ) from e

    def _get_full_log(self, job_name: str, build_number: int) -> List[str]:
        """Get the complete console log"""
        try:
            log_text = self.connection.client.get_build_console_output(
                job_name, build_number
            )
            return log_text.splitlines()
        except Exception as e:
            logger.error(f"Failed to get full log via python-jenkins: {e}")
            # Fallback to direct HTTP request
            return self._get_log_via_http(job_name, build_number)

    def _get_progressive_log(
        self, job_name: str, build_number: int, start_line: int, end_line: Optional[int]
    ) -> List[str]:
        """Get log lines using progressive API"""
        url = f"{self.connection.config.url}/job/{job_name}/{build_number}/logText/progressiveText"
        params = {"start": start_line * 100}  # Approximate byte offset

        try:
            response = self.connection.session.get(
                url, params=params, timeout=self.connection.config.timeout
            )
            response.raise_for_status()

            lines = response.text.splitlines()

            if end_line is not None and end_line < len(lines):
                lines = lines[: end_line - start_line]

            return lines

        except requests.RequestException as e:
            logger.error(f"Progressive log fetch failed: {e}")
            # Fallback to full log and slice
            full_log = self._get_full_log(job_name, build_number)
            return full_log[start_line:end_line]

    def _get_log_via_http(self, job_name: str, build_number: int) -> List[str]:
        """Get log via direct HTTP request"""
        url = f"{self.connection.config.url}/job/{job_name}/{build_number}/consoleText"

        try:
            response = self.connection.session.get(
                url, timeout=self.connection.config.timeout
            )
            response.raise_for_status()
            return response.text.splitlines()

        except requests.RequestException as e:
            raise JenkinsConnectionError(f"HTTP log fetch failed: {e}") from e

    def get_log_size(self, job_name: str, build_number: int) -> int:
        """Get the number of lines in the console log"""
        try:
            lines = self.get_console_log(job_name, build_number)
            return len(lines)
        except Exception as e:
            logger.error(f"Failed to get log size: {e}")
            return 0

    def get_log_chunk(
        self,
        job_name: str,
        build_number: int,
        start_byte: int = 0,
        max_bytes: int = 1024 * 1024,  # 1MB default
    ) -> str:
        """Get a chunk of log content by byte range for streaming large logs"""
        url = f"{self.connection.config.url}/job/{job_name}/{build_number}/logText/progressiveText"
        params = {"start": start_byte}

        try:
            response = self.connection.session.get(
                url, params=params, timeout=self.connection.config.timeout, stream=True
            )
            response.raise_for_status()

            # Read up to max_bytes
            content = ""
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if bytes_read + len(chunk.encode("utf-8")) > max_bytes:
                    # Take only what fits in the limit
                    remaining = max_bytes - bytes_read
                    if remaining > 0:
                        # This is approximate since we're dealing with unicode
                        content += chunk[:remaining]
                    break
                content += chunk
                bytes_read += len(chunk.encode("utf-8"))

            return content

        except requests.RequestException as e:
            raise JenkinsConnectionError(f"Chunked log fetch failed: {e}") from e

    def stream_log_lines(
        self,
        job_name: str,
        build_number: int,
        poll_interval: float = 2.0,
        max_lines: Optional[int] = None,
    ):
        """Generator that yields new log lines as they appear (for live builds)"""
        current_line = 0
        lines_yielded = 0

        while True:
            try:
                # Get log from current position
                new_lines = self.get_console_log(
                    job_name, build_number, start_line=current_line
                )

                if new_lines:
                    for line in new_lines:
                        yield line
                        current_line += 1
                        lines_yielded += 1

                        if max_lines and lines_yielded >= max_lines:
                            return

                # Check if build is still running
                try:
                    from .build_manager import BuildManager

                    build_manager = BuildManager(self.connection)
                    build_info = build_manager.get_build_info(job_name, build_number)
                    if build_info.status not in ["BUILDING", "STARTED"]:
                        # Build completed, return any remaining lines
                        break
                except Exception as e:
                    logger.warning(f"Could not check build status: {e}")
                    break

                import time

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error streaming log: {e}")
                break
