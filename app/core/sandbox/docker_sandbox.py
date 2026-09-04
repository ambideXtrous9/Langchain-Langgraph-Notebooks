"""Docker Sandbox Backend for Deep Agents.

Runs untrusted code and bash commands in a strictly isolated Docker container:
1. Hardware Limits: Memory ceiling (--memory=512m) and CPU throttling (--cpus=1.0).
2. Network Isolation: Optional network sandbox (--network none / restricted).
3. Lifecycle Management: Automatic startup and ephemeral teardown.
4. Resilient Fallback: Automatically falls back to IsolatedSubprocessSandbox if Docker daemon is unreachable.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.sandbox.base import BaseSandbox
from app.core.sandbox.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from app.core.sandbox.subprocess_sandbox import IsolatedSubprocessSandbox

logger = logging.getLogger(__name__)


def is_docker_available() -> bool:
    """Checks if the docker CLI and daemon are accessible."""
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=3,
        )
        return res.returncode == 0
    except Exception:
        return False


class DockerSandbox(BaseSandbox):
    """Containerized sandbox executing commands inside an isolated Docker container."""

    def __init__(
        self,
        image: str = "python:3.12-slim",
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        network: str = "none",
        default_timeout: int = 30,
        cleanup_on_exit: bool = True,
    ):
        self._id = f"sandbox-docker-{uuid.uuid4().hex[:10]}"
        self._image = image
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._network = network
        self._default_timeout = default_timeout
        self._cleanup_on_exit = cleanup_on_exit
        self._container_id: Optional[str] = None
        self._fallback_sandbox: Optional[IsolatedSubprocessSandbox] = None

        if not is_docker_available():
            logger.warning("[DockerSandbox] Docker daemon not reachable. Using IsolatedSubprocessSandbox fallback.")
            self._fallback_sandbox = IsolatedSubprocessSandbox(default_timeout=default_timeout)
            return

        try:
            self._start_container()
        except Exception as e:
            logger.warning(f"[DockerSandbox] Failed to start container ({e}). Falling back to IsolatedSubprocessSandbox.")
            self._fallback_sandbox = IsolatedSubprocessSandbox(default_timeout=default_timeout)

    @property
    def id(self) -> str:
        if self._fallback_sandbox:
            return self._fallback_sandbox.id
        return self._id

    def _start_container(self) -> None:
        """Starts an ephemeral docker container with resource constraints."""
        cmd = [
            "docker", "run", "-d", "--rm",
            "--name", self._id,
            f"--memory={self._memory_limit}",
            f"--cpus={self._cpu_limit}",
            f"--network={self._network}",
            "-w", "/workspace",
            self._image,
            "tail", "-f", "/dev/null",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            raise RuntimeError(f"Docker run failed: {res.stderr}")
        self._container_id = res.stdout.strip()
        logger.info(f"[DockerSandbox] Container {self._id} started (ID: {self._container_id[:12]})")

        # Initialize workspace
        subprocess.run(["docker", "exec", self._id, "mkdir", "-p", "/workspace"], check=False)

    def execute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
        """Executes a command inside the running docker container."""
        if self._fallback_sandbox:
            return self._fallback_sandbox.execute(command, timeout=timeout)

        if not self._container_id:
            return ExecuteResponse(output="Error: Docker container is not active.", exit_code=1)

        effective_timeout = timeout if timeout is not None else self._default_timeout
        exec_cmd = [
            "docker", "exec",
            "-i",
            "-w", "/workspace",
            self._id,
            "sh", "-c", command,
        ]

        try:
            res = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            output_parts = []
            if res.stdout:
                output_parts.append(res.stdout)
            if res.stderr:
                for line in res.stderr.splitlines():
                    output_parts.append(f"[stderr] {line}")
            output = "\n".join(output_parts) if output_parts else "<no output>"

            return ExecuteResponse(
                output=output,
                exit_code=res.returncode,
                truncated=False,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Error: Command timed out after {effective_timeout}s.",
                exit_code=124,
                truncated=False,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing in Docker container ({type(e).__name__}): {e}",
                exit_code=1,
                truncated=False,
            )

    def upload_files(self, files: List[Tuple[str, bytes]]) -> List[FileUploadResponse]:
        """Uploads files into the container's /workspace."""
        if self._fallback_sandbox:
            return self._fallback_sandbox.upload_files(files)

        responses: List[FileUploadResponse] = []
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            for rel_path, content in files:
                try:
                    fpath = temp_path / rel_path
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    fpath.write_bytes(content)

                    # Ensure parent dir exists in container
                    parent_in_container = f"/workspace/{Path(rel_path).parent}"
                    subprocess.run(
                        ["docker", "exec", self._id, "mkdir", "-p", str(parent_in_container)],
                        check=False,
                    )
                    # Copy to container
                    dest = f"{self._id}:/workspace/{rel_path}"
                    res = subprocess.run(["docker", "cp", str(fpath), dest], capture_output=True)
                    if res.returncode == 0:
                        responses.append(FileUploadResponse(path=rel_path, error=None))
                    else:
                        responses.append(FileUploadResponse(path=rel_path, error=res.stderr.decode()))
                except Exception as e:
                    responses.append(FileUploadResponse(path=rel_path, error=str(e)))
        return responses

    def download_files(self, paths: List[str]) -> List[FileDownloadResponse]:
        """Downloads files from the container's /workspace."""
        if self._fallback_sandbox:
            return self._fallback_sandbox.download_files(paths)

        responses: List[FileDownloadResponse] = []
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            for rel_path in paths:
                try:
                    local_dest = temp_path / Path(rel_path).name
                    src = f"{self._id}:/workspace/{rel_path}"
                    res = subprocess.run(["docker", "cp", src, str(local_dest)], capture_output=True)
                    if res.returncode == 0 and local_dest.exists():
                        content = local_dest.read_bytes()
                        responses.append(FileDownloadResponse(path=rel_path, content=content, error=None))
                    else:
                        responses.append(FileDownloadResponse(path=rel_path, error="file_not_found"))
                except Exception as e:
                    responses.append(FileDownloadResponse(path=rel_path, error=str(e)))
        return responses

    def cleanup(self) -> None:
        """Stops and removes the container."""
        if self._fallback_sandbox:
            self._fallback_sandbox.cleanup()
            return

        if self._container_id:
            try:
                subprocess.run(["docker", "rm", "-f", self._id], capture_output=True, timeout=5)
                logger.info(f"[DockerSandbox] Container {self._id} terminated.")
            except Exception as e:
                logger.warning(f"Error terminating docker container {self._id}: {e}")
            self._container_id = None

    def __del__(self):
        if self._cleanup_on_exit:
            self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup_on_exit:
            self.cleanup()


__all__ = ["DockerSandbox", "is_docker_available"]
