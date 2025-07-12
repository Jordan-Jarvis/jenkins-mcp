"""
Jenkins Job Name Utilities

Handles various formats of Jenkins job names with URL encoding/decoding,
normalization, and conversion between different representations.

"""

import re
import urllib.parse
from typing import Optional, Tuple

from ..logging_config import get_component_logger

logger = get_component_logger("jenkins.job_name_utils")


class JobNameParser:
    """Handles parsing and normalization of Jenkins job names"""

    @staticmethod
    def normalize_job_name(job_name: str) -> str:
        """
        Normalize a job name to standard Jenkins format

        Args:
            job_name: Job name in various formats

        Returns:
            Normalized job name without /job/ prefixes and URL decoded
        """
        if not job_name:
            return ""

        # Start with the input
        normalized = job_name.strip()

        # Remove leading slash if present
        if normalized.startswith("/"):
            normalized = normalized[1:]

        # Handle URL decoding carefully - preserve single-encoded slashes in job names
        # %252F (double-encoded) -> %2F (single-encoded, preserve this)
        # %2F (single-encoded) -> / (only decode if it's clearly a folder separator)
        original = normalized

        # First pass: decode double-encoding (%252F -> %2F)
        if "%252F" in normalized:
            normalized = urllib.parse.unquote(normalized)
            logger.debug(f"Double-decode: {original} -> {normalized}")

        # Don't fully decode %2F in job names - these are often part of the actual job name
        # Only decode if we're sure it's a folder separator (not implemented yet, keeping %2F)

        # Remove /job/ prefixes - convert job/QA_JOBS/job/release to QA_JOBS/release
        # Split by / and filter out 'job' segments
        parts = [part for part in normalized.split("/") if part and part != "job"]
        normalized = "/".join(parts)

        logger.debug(f"Normalized job name: '{job_name}' -> '{normalized}'")
        return normalized

    @staticmethod
    def to_jenkins_api_path(job_name: str) -> str:
        """
        Convert job name to Jenkins API path format

        Args:
            job_name: Normalized job name

        Returns:
            Jenkins API path format
        """
        normalized = JobNameParser.normalize_job_name(job_name)
        if not normalized:
            return ""

        # Split by / but be careful not to split on encoded slashes (%2F)
        parts = normalized.split("/")
        api_parts = []
        for part in parts:
            if part:  # Skip empty parts
                api_parts.extend(["job", part])

        api_path = "/".join(api_parts)
        logger.debug(f"API path: '{job_name}' -> '{api_path}'")
        return api_path

    @staticmethod
    def to_blue_ocean_path(job_name: str) -> str:
        """
        Convert job name to Blue Ocean API path format

        Args:
            job_name: Job name in any format

        Returns:
            Blue Ocean path (e.g., QA_JOBS/pipelines/master)
        """
        normalized = JobNameParser.normalize_job_name(job_name)
        if not normalized:
            return ""

        parts = normalized.split("/")
        if len(parts) <= 1:
            return normalized

        # Note: The last part contains %2F which should NOT get /pipelines/ inserted
        bo_path = parts[0]  # First part stays as-is
        for i, part in enumerate(parts[1:], 1):
            if part:
                # Only add /pipelines/ if this is a true folder separator, not an encoded slash
                if i == len(parts) - 1 and "%2F" in part:
                    # Last part with encoded slash - don't add pipelines
                    bo_path += f"/{part}"
                else:
                    bo_path += f"/pipelines/{part}"

        logger.debug(f"Blue Ocean path: '{job_name}' -> '{bo_path}'")
        return bo_path

    @staticmethod
    def extract_from_url(jenkins_url: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Extract job name and build number from a Jenkins URL

        Args:
            jenkins_url: Full Jenkins URL (e.g., https://jenkins.com/job/QA_JOBS/job/release%252F2.2.0/328/)

        Returns:
            Tuple of (job_name, build_number) or (None, None) if parsing fails
        """
        if not jenkins_url:
            return None, None

        try:
            # Pattern to match Jenkins URLs with job names and build numbers
            # Matches: /job/QA_JOBS/job/release%252F2.2.0/328/
            pattern = r"/job/([^/]+(?:/job/[^/]+)*)/(\d+)/?(?:\?|$|#)"

            # More flexible pattern to handle various formats
            alt_pattern = r"/job/(.+?)/(\d+)/?(?:\?|$|#|/)"

            match = re.search(pattern, jenkins_url)
            if not match:
                match = re.search(alt_pattern, jenkins_url)

            if match:
                job_path = match.group(1)
                build_number = int(match.group(2))

                # Normalize the job path
                normalized_job = JobNameParser.normalize_job_name(job_path)

                logger.debug(
                    f"Extracted from URL: '{jenkins_url}' -> job='{normalized_job}', build={build_number}"
                )
                return normalized_job, build_number

            logger.warning(
                f"Could not extract job name and build number from URL: {jenkins_url}"
            )
            return None, None

        except Exception as e:
            logger.error(f"Error parsing Jenkins URL '{jenkins_url}': {e}")
            return None, None

    @staticmethod
    def is_encoded(text: str) -> bool:
        """Check if text contains URL encoding"""
        return "%" in text and any(
            char in text for char in ["%2F", "%252F", "%20", "%3A"]
        )

    @staticmethod
    def safe_decode(text: str) -> str:
        """Safely decode URL-encoded text with fallback"""
        if not JobNameParser.is_encoded(text):
            return text

        try:
            # Try multiple levels of decoding
            decoded = text
            for _ in range(3):
                new_decoded = urllib.parse.unquote(decoded)
                if new_decoded == decoded:
                    break
                decoded = new_decoded
            return decoded
        except Exception as e:
            logger.debug(f"URL decode failed for '{text}': {e}")
            return text

    @staticmethod
    def format_for_display(job_name: str) -> str:
        """Format job name for human-readable display"""
        normalized = JobNameParser.normalize_job_name(job_name)
        return normalized.replace("/", " › ")


# Convenience functions for backwards compatibility
def normalize_job_name(job_name: str) -> str:
    """Normalize job name - convenience function"""
    return JobNameParser.normalize_job_name(job_name)


def extract_job_from_url(jenkins_url: str) -> Tuple[Optional[str], Optional[int]]:
    """Extract job name and build number from URL - convenience function"""
    return JobNameParser.extract_from_url(jenkins_url)
