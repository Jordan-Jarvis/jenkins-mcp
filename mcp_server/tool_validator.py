"""CLI tool for validating tool implementations"""

import argparse
import os

from .config import JenkinsConfig
from .config_factory import ConfigFactory
from .di_container import DIContainer
from .tool_factory import ToolFactory


def validate_all_tools(use_real_jenkins=False):
    """Validate all tool implementations"""
    try:
        if use_real_jenkins:
            # Use real Jenkins credentials from test_jenkins_info.txt
            jenkins_config = JenkinsConfig(
                url="https://jenkins.example.com",
                username="your.username@example.com",
                token="your-api-token-here",
                verify_ssl=True,
            )
            config = ConfigFactory.create_test_config(jenkins_config=jenkins_config)
        else:
            config = ConfigFactory.create_test_config()

        container = DIContainer(config)
        factory = ToolFactory(container)
        tools = factory.create_tools()

        print(f"Validating {len(tools)} tools...")

        for name, tool in tools.items():
            try:
                # Validate tool definition
                schema = tool.to_mcp_schema()
                print(f"✓ {name}: Valid")

                # Test parameter validation
                if tool.parameters:
                    print(f"  Parameters: {len(tool.parameters)}")
                    for param in tool.parameters:
                        print(
                            f"    - {param.name} ({param.param_type.__name__}): {param.description}"
                        )

            except Exception as e:
                print(f"✗ {name}: {e}")
                return False

        print("All tools are valid!")
        return True

    except Exception as e:
        print(f"Validation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate tool implementations")
    parser.add_argument(
        "--real-jenkins",
        action="store_true",
        help="Use real Jenkins credentials for validation",
    )
    args = parser.parse_args()

    success = validate_all_tools(use_real_jenkins=args.real_jenkins)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
