from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar


@dataclass
class Build:
    job_name: str
    build_number: int
    status: Optional[str] = "UNKNOWN"
    url: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    sub_builds: List["SubBuild"] = field(default_factory=list)
    log_path: Optional[str] = None


@dataclass
class SubBuild:
    job_name: str
    build_number: int
    url: Optional[str] = None
    status: Optional[str] = "UNKNOWN"
    parent: Optional[Build] = None
    parent_job_name: Optional[str] = None
    parent_build_number: Optional[int] = None
    depth: int = 0
    log_path: Optional[str] = None


@dataclass
class LogContext:
    build: Build
    start_line: int
    end_line: int
    lines: List[str]


@dataclass
class ErrorBlock:
    build: Build
    pattern: str
    context: LogContext


@dataclass
class VectorChunk:
    build: Build
    chunk_index: int
    text: str
    vector: List[float] = field(default_factory=list)


T = TypeVar("T")


@dataclass
class ParameterSpec:
    """Specification for a tool parameter"""

    name: str
    param_type: Type
    description: str
    required: bool = True
    default: Any = None

    def validate(self, value: Any) -> Any:
        """Validate and convert parameter value"""
        if value is None and self.required:
            raise ValueError(f"Required parameter '{self.name}' is missing")

        if value is None and not self.required:
            return self.default

        # Type validation and conversion
        if not isinstance(value, self.param_type):
            try:
                return self.param_type(value)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Parameter '{self.name}' must be {self.param_type.__name__}: {e}"
                )

        return value


@dataclass
class ToolResult(Generic[T]):
    """Standardized tool result"""

    success: bool
    data: Optional[T] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: Optional[float] = None

    @classmethod
    def success_result(
        cls, data: T, execution_time_ms: Optional[float] = None
    ) -> "ToolResult[T]":
        return cls(success=True, data=data, execution_time_ms=execution_time_ms)

    @classmethod
    def error_result(
        cls, error: Exception, execution_time_ms: Optional[float] = None
    ) -> "ToolResult[T]":
        return cls(
            success=False,
            error_message=str(error),
            error_type=type(error).__name__,
            execution_time_ms=execution_time_ms,
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success, "execution_time_ms": self.execution_time_ms}
        if self.data is not None:
            result["data"] = self.data
        if self.error_message:
            result["error_message"] = self.error_message
            result["error_type"] = self.error_type
        return result

    def unwrap(self) -> T:
        """Unwrap the result data or raise the error

        Returns:
            The wrapped data if successful

        Raises:
            Exception: If the result represents an error
        """
        if self.success:
            return self.data
        else:
            # Try to recreate the original exception type if possible
            from .exceptions import JenkinsMCPError

            error_msg = self.error_message or "Unknown error"
            if self.error_type:
                # For now, just raise a generic JenkinsMCPError with type info
                raise JenkinsMCPError(f"{self.error_type}: {error_msg}")
            else:
                raise JenkinsMCPError(error_msg)


class Manager(ABC):
    @abstractmethod
    def initialize(self):
        pass


class Tool(ABC, Generic[T]):
    """Enhanced base class for all tools"""

    def __init__(self):
        self._validate_tool_definition()

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used for registration)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> List[ParameterSpec]:
        """Tool parameter specifications"""
        pass

    @abstractmethod
    def _execute_impl(self, **kwargs) -> T:
        """Tool-specific implementation"""
        pass

    def _validate_tool_definition(self) -> None:
        """Validate tool definition at initialization"""
        from .exceptions import ConfigurationError

        if not self.name:
            raise ConfigurationError(
                f"Tool {self.__class__.__name__} must define a name"
            )
        if not self.description:
            raise ConfigurationError(
                f"Tool {self.__class__.__name__} must define a description"
            )

    def validate_parameters(self, **kwargs) -> Dict[str, Any]:
        """Validate and convert input parameters"""
        from .logging_config import get_component_logger

        logger = get_component_logger(f"tool.{self.name}")

        validated_params = {}
        param_specs = {param.name: param for param in self.parameters}

        # Validate provided parameters
        for name, value in kwargs.items():
            if name not in param_specs:
                logger.warning(f"Unknown parameter '{name}' for tool {self.name}")
                continue

            validated_params[name] = param_specs[name].validate(value)

        # Check for missing required parameters and add defaults
        for param_spec in self.parameters:
            if param_spec.name not in validated_params:
                if param_spec.required:
                    if param_spec.default is not None:
                        validated_params[param_spec.name] = param_spec.default
                    else:
                        raise ValueError(
                            f"Required parameter '{param_spec.name}' is missing"
                        )
                elif param_spec.default is not None:
                    # Add default for optional parameters
                    validated_params[param_spec.name] = param_spec.default

        return validated_params

    def execute(self, **kwargs) -> ToolResult[T]:
        """Execute the tool with standardized error handling and validation"""
        import time

        from .logging_config import get_component_logger

        logger = get_component_logger(f"tool.{self.name}")
        start_time = time.time()

        try:
            logger.info(f"Executing tool: {self.name}")

            # Validate parameters
            validated_params = self.validate_parameters(**kwargs)

            # Execute implementation
            result = self._execute_impl(**validated_params)

            execution_time = (time.time() - start_time) * 1000
            logger.info(
                f"Tool {self.name} completed successfully in {execution_time:.2f}ms"
            )

            return ToolResult.success_result(result, execution_time)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                f"Tool {self.name} failed after {execution_time:.2f}ms: {e}",
                exc_info=True,
            )
            return ToolResult.error_result(e, execution_time)

    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert tool to MCP schema format"""
        properties = {}
        required = []

        for param in self.parameters:
            param_schema = {
                "type": self._python_type_to_json_schema(param.param_type),
                "description": param.description,
            }

            if param.default is not None:
                param_schema["default"] = param.default

            properties[param.name] = param_schema

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def _python_type_to_json_schema(self, python_type: Type) -> str:
        """Convert Python type to JSON schema type"""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_mapping.get(python_type, "string")


# Legacy Tool class for backward compatibility
class LegacyTool(ABC):
    """Legacy base class for backward compatibility"""

    NAME: str
    DESCRIPTION: str
    PARAMS_SCHEMA: dict

    @abstractmethod
    def _execute_impl(self, *args, **kwargs) -> Any:
        """Implementation-specific execution logic"""
        pass

    def execute(self, *args, **kwargs) -> Any:
        """Execute the tool with standardized error handling"""
        from .logging_config import get_component_logger

        logger = get_component_logger(f"tool.{self.NAME}")

        try:
            logger.info(f"Executing tool: {self.NAME}")
            result = self._execute_impl(*args, **kwargs)
            logger.info(f"Tool {self.NAME} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {self.NAME} failed: {e}", exc_info=True)
            raise
