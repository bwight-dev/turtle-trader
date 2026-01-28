"""Unit tests for Docker configuration files."""

import os
import subprocess
from pathlib import Path

import pytest


# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestDockerfileExists:
    """Tests for Dockerfile existence and basic validation."""

    def test_dockerfile_exists(self):
        """Dockerfile exists in project root."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found"

    def test_dockerfile_has_content(self):
        """Dockerfile is not empty."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert len(content) > 100, "Dockerfile appears to be empty or too short"

    def test_dockerfile_has_from_instruction(self):
        """Dockerfile has FROM instruction."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "FROM" in content, "Dockerfile missing FROM instruction"

    def test_dockerfile_uses_python_312(self):
        """Dockerfile uses Python 3.12."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "python:3.12" in content, "Dockerfile should use Python 3.12"

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile has HEALTHCHECK instruction."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Dockerfile missing HEALTHCHECK"

    def test_dockerfile_has_non_root_user(self):
        """Dockerfile creates non-root user for security."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "useradd" in content or "USER" in content, (
            "Dockerfile should create non-root user"
        )


class TestDockerComposeExists:
    """Tests for docker-compose.yml existence and validation."""

    def test_docker_compose_exists(self):
        """docker-compose.yml exists in project root."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        assert compose.exists(), "docker-compose.yml not found"

    def test_docker_compose_has_services(self):
        """docker-compose.yml defines services."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "services:" in content, "docker-compose.yml missing services"

    def test_docker_compose_has_turtle_bot(self):
        """docker-compose.yml has turtle-bot service."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "turtle-bot:" in content, "docker-compose.yml missing turtle-bot service"

    def test_docker_compose_has_environment_vars(self):
        """docker-compose.yml configures environment variables."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "environment:" in content, "docker-compose.yml missing environment config"
        assert "DATABASE_URL" in content, "Missing DATABASE_URL in environment"

    def test_docker_compose_has_volumes(self):
        """docker-compose.yml configures volumes."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "volumes:" in content, "docker-compose.yml missing volumes"

    def test_docker_compose_has_healthcheck(self):
        """docker-compose.yml has healthcheck configuration."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "healthcheck:" in content, "docker-compose.yml missing healthcheck"


class TestDeployScript:
    """Tests for deploy.sh script."""

    def test_deploy_script_exists(self):
        """deploy.sh exists in scripts directory."""
        deploy = PROJECT_ROOT / "scripts" / "deploy.sh"
        assert deploy.exists(), "deploy.sh not found"

    def test_deploy_script_is_executable(self):
        """deploy.sh is executable."""
        deploy = PROJECT_ROOT / "scripts" / "deploy.sh"
        assert os.access(deploy, os.X_OK), "deploy.sh is not executable"

    def test_deploy_script_has_shebang(self):
        """deploy.sh has proper shebang."""
        deploy = PROJECT_ROOT / "scripts" / "deploy.sh"
        content = deploy.read_text()
        assert content.startswith("#!/bin/bash"), "deploy.sh missing bash shebang"

    def test_deploy_script_has_commands(self):
        """deploy.sh has expected commands."""
        deploy = PROJECT_ROOT / "scripts" / "deploy.sh"
        content = deploy.read_text()
        expected_commands = ["build", "start", "stop", "logs", "deploy"]
        for cmd in expected_commands:
            assert cmd in content, f"deploy.sh missing '{cmd}' command"

    def test_deploy_script_help(self):
        """deploy.sh shows help when run with no args."""
        deploy = PROJECT_ROOT / "scripts" / "deploy.sh"
        result = subprocess.run(
            [str(deploy), "help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"deploy.sh help failed: {result.stderr}"
        assert "Usage:" in result.stdout, "Help output missing Usage section"


class TestEnvExample:
    """Tests for .env.example file."""

    def test_env_example_exists(self):
        """.env.example exists in project root."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example not found"

    def test_env_example_has_database_url(self):
        """.env.example includes DATABASE_URL."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "DATABASE_URL" in content, ".env.example missing DATABASE_URL"

    def test_env_example_has_ibkr_config(self):
        """.env.example includes IBKR configuration."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "IBKR_HOST" in content, ".env.example missing IBKR_HOST"
        assert "IBKR_PORT" in content, ".env.example missing IBKR_PORT"

    def test_env_example_has_trading_config(self):
        """.env.example includes trading configuration."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "TRADING_MODE" in content or "DRY_RUN" in content, (
            ".env.example missing trading config"
        )


class TestDockerBuild:
    """Tests for Docker build (requires Docker to be installed)."""

    @pytest.mark.skip(reason="Requires Docker daemon - run manually")
    def test_docker_builds_successfully(self):
        """Docker image builds without errors."""
        result = subprocess.run(
            ["docker", "build", "-t", "turtle-bot-test", "."],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"

    @pytest.mark.skip(reason="Requires Docker daemon - run manually")
    def test_docker_compose_config_valid(self):
        """docker-compose.yml is valid."""
        result = subprocess.run(
            ["docker", "compose", "config"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"docker-compose config invalid: {result.stderr}"
