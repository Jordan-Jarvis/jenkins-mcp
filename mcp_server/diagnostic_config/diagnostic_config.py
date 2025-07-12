"""
Diagnostic Configuration Loader

This module loads and provides access to diagnostic parameters from YAML configuration,
replacing hard-coded values in the diagnose_build_failure tool.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from dataclasses import dataclass, field

from ..logging_config import get_component_logger

logger = get_component_logger("config.diagnostic")


@dataclass
class SemanticSearchConfig:
    """Configuration for semantic search functionality"""

    search_queries: List[str] = field(default_factory=list)
    max_results_per_query: int = 2
    max_total_highlights: int = 5
    min_content_length: int = 50
    min_diagnostic_score: float = 0.6
    max_content_preview: int = 400


@dataclass
class FailurePatternsConfig:
    """Configuration for failure pattern recognition"""

    stack_trace_patterns: List[str] = field(default_factory=list)
    max_fallback_patterns: int = 3
    max_pattern_preview: int = 200


@dataclass
class PatternRecommendation:
    """Single pattern-based recommendation"""

    conditions: List[Union[str, List[str]]] = field(default_factory=list)
    message: str = ""


@dataclass
class RecommendationsConfig:
    """Configuration for recommendation engine"""

    patterns: Dict[str, PatternRecommendation] = field(default_factory=dict)
    priority_jobs: Dict[str, Any] = field(default_factory=dict)
    investigation_guidance: str = ""
    max_recommendations: int = 6


@dataclass
class BuildProcessingConfig:
    """Configuration for build processing"""

    parallel: Dict[str, int] = field(default_factory=dict)
    chunks: Dict[str, int] = field(default_factory=dict)


@dataclass
class SummaryConfig:
    """Configuration for summary generation"""

    max_failures_displayed: int = 5
    failure_list_template: str = "  - {job_name} #{build_number} ({status})\n"
    overflow_message_template: str = "  ... and {count} more failures\n"
    success_rate_precision: int = 1


@dataclass
class ContextConfig:
    """Configuration for context and token management"""

    max_tokens_total: int = 10000
    max_tokens_per_chunk: int = 1000
    truncation_threshold: int = 8000
    high_value_chunk_threshold: float = 0.7
    chunk_scoring_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class DiagnosticConfig:
    """Main diagnostic configuration container"""

    semantic_search: SemanticSearchConfig = field(default_factory=SemanticSearchConfig)
    failure_patterns: FailurePatternsConfig = field(
        default_factory=FailurePatternsConfig
    )
    recommendations: RecommendationsConfig = field(
        default_factory=RecommendationsConfig
    )
    build_processing: BuildProcessingConfig = field(
        default_factory=BuildProcessingConfig
    )
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    log_processing: Dict[str, Any] = field(default_factory=dict)
    heuristics: Dict[str, Any] = field(default_factory=dict)
    error_analysis: Dict[str, Any] = field(default_factory=dict)
    vector_search: Dict[str, Any] = field(default_factory=dict)
    display: Dict[str, Any] = field(default_factory=dict)
    debugging: Dict[str, Any] = field(default_factory=dict)


class DiagnosticConfigLoader:
    """Loads and manages diagnostic configuration from YAML"""

    _instance: Optional["DiagnosticConfigLoader"] = None
    _config: Optional[DiagnosticConfig] = None

    def __new__(cls) -> "DiagnosticConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        config_path = self._get_config_path()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)

            self._config = self._parse_config(yaml_data)
            logger.info(f"Loaded diagnostic configuration from {config_path}")

        except FileNotFoundError:
            logger.warning(
                f"Diagnostic config file not found at {config_path}, using defaults"
            )
            self._config = DiagnosticConfig()
        except Exception as e:
            logger.error(f"Failed to load diagnostic config: {e}")
            self._config = DiagnosticConfig()

    def _get_config_path(self) -> Path:
        """Get the path to the diagnostic configuration file"""
        # Check for user-specified config path via environment variable
        custom_config = os.getenv("JENKINS_MCP_DIAGNOSTIC_CONFIG")
        if custom_config:
            custom_path = Path(custom_config)
            if custom_path.exists():
                logger.info(f"Using custom diagnostic config: {custom_path}")
                return custom_path
            else:
                logger.warning(f"Custom diagnostic config not found: {custom_path}")

        # Check for config in project config directory (for development/user overrides)
        project_root = Path(__file__).parent.parent.parent
        user_config_path = project_root / "config" / "diagnostic-parameters.yml"
        if user_config_path.exists():
            logger.info(f"Using user diagnostic config: {user_config_path}")
            return user_config_path

        # Use bundled default config (shipped with package)
        bundled_config_path = Path(__file__).parent / "diagnostic-parameters.yml"
        if bundled_config_path.exists():
            logger.info(f"Using bundled diagnostic config: {bundled_config_path}")
            return bundled_config_path

        # Fallback: create minimal default
        logger.warning("No diagnostic config found, using minimal defaults")
        return bundled_config_path  # Will be created with defaults

    def _parse_config(self, yaml_data: Dict[str, Any]) -> DiagnosticConfig:
        """Parse YAML data into configuration objects"""
        config = DiagnosticConfig()

        # Parse semantic search config
        if "semantic_search" in yaml_data:
            ss_data = yaml_data["semantic_search"]
            config.semantic_search = SemanticSearchConfig(
                search_queries=ss_data.get("search_queries", []),
                max_results_per_query=ss_data.get("max_results_per_query", 2),
                max_total_highlights=ss_data.get("max_total_highlights", 5),
                min_content_length=ss_data.get("min_content_length", 50),
                min_diagnostic_score=ss_data.get("min_diagnostic_score", 0.6),
                max_content_preview=ss_data.get("max_content_preview", 400),
            )

        # Parse failure patterns config
        if "failure_patterns" in yaml_data:
            fp_data = yaml_data["failure_patterns"]
            config.failure_patterns = FailurePatternsConfig(
                stack_trace_patterns=fp_data.get("stack_trace_patterns", []),
                max_fallback_patterns=fp_data.get("max_fallback_patterns", 3),
                max_pattern_preview=fp_data.get("max_pattern_preview", 200),
            )

        # Parse recommendations config
        if "recommendations" in yaml_data:
            rec_data = yaml_data["recommendations"]

            # Parse pattern recommendations
            patterns = {}
            if "patterns" in rec_data:
                for pattern_name, pattern_data in rec_data["patterns"].items():
                    patterns[pattern_name] = PatternRecommendation(
                        conditions=pattern_data.get("conditions", []),
                        message=pattern_data.get("message", ""),
                    )

            config.recommendations = RecommendationsConfig(
                patterns=patterns,
                priority_jobs=rec_data.get("priority_jobs", {}),
                investigation_guidance=rec_data.get("investigation_guidance", ""),
                max_recommendations=rec_data.get("max_recommendations", 6),
            )

        # Parse build processing config
        if "build_processing" in yaml_data:
            bp_data = yaml_data["build_processing"]
            config.build_processing = BuildProcessingConfig(
                parallel=bp_data.get("parallel", {}), chunks=bp_data.get("chunks", {})
            )

        # Parse summary config
        if "summary" in yaml_data:
            sum_data = yaml_data["summary"]
            config.summary = SummaryConfig(
                max_failures_displayed=sum_data.get("max_failures_displayed", 5),
                failure_list_template=sum_data.get(
                    "failure_list_template",
                    "  - {job_name} #{build_number} ({status})\n",
                ),
                overflow_message_template=sum_data.get(
                    "overflow_message_template", "  ... and {count} more failures\n"
                ),
                success_rate_precision=sum_data.get("success_rate_precision", 1),
            )

        # Parse context config
        if "context" in yaml_data:
            ctx_data = yaml_data["context"]
            config.context = ContextConfig(
                max_tokens_total=ctx_data.get("max_tokens_total", 10000),
                max_tokens_per_chunk=ctx_data.get("max_tokens_per_chunk", 1000),
                truncation_threshold=ctx_data.get("truncation_threshold", 8000),
                high_value_chunk_threshold=ctx_data.get(
                    "high_value_chunk_threshold", 0.7
                ),
                chunk_scoring_weights=ctx_data.get("chunk_scoring_weights", {}),
            )

        # Store remaining sections as dictionaries for direct access
        config.log_processing = yaml_data.get("log_processing", {})
        config.heuristics = yaml_data.get("heuristics", {})
        config.error_analysis = yaml_data.get("error_analysis", {})
        config.vector_search = yaml_data.get("vector_search", {})
        config.display = yaml_data.get("display", {})
        config.debugging = yaml_data.get("debugging", {})

        return config

    @property
    def config(self) -> DiagnosticConfig:
        """Get the current configuration"""
        if self._config is None:
            self._load_config()
        return self._config

    def reload(self) -> None:
        """Reload configuration from file"""
        self._config = None
        self._load_config()

    def get_semantic_search_queries(self) -> List[str]:
        """Get semantic search query patterns"""
        return self.config.semantic_search.search_queries

    def get_failure_patterns(self) -> List[str]:
        """Get failure pattern list for fallback analysis"""
        return self.config.failure_patterns.stack_trace_patterns

    def get_pattern_recommendations(self) -> Dict[str, PatternRecommendation]:
        """Get pattern-based recommendations mapping"""
        return self.config.recommendations.patterns

    def get_investigation_guidance(self) -> str:
        """Get standard investigation guidance text"""
        return self.config.recommendations.investigation_guidance

    def get_build_processing_limits(self) -> Dict[str, int]:
        """Get build processing limits"""
        return {
            **self.config.build_processing.parallel,
            **self.config.build_processing.chunks,
        }

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get a configuration value by dot-separated path"""
        try:
            parts = path.split(".")
            value = self.config

            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default

            return value
        except Exception:
            return default


# Global configuration instance
_config_loader: Optional[DiagnosticConfigLoader] = None


def get_diagnostic_config() -> DiagnosticConfigLoader:
    """Get the global diagnostic configuration instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = DiagnosticConfigLoader()
    return _config_loader


def reload_diagnostic_config() -> None:
    """Reload the diagnostic configuration from file"""
    if _config_loader is not None:
        _config_loader.reload()
