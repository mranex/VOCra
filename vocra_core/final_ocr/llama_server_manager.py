from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

import requests


class LlamaServerManager:
    def __init__(
        self,
        *,
        llama_cpp_dir: str,
        model_path: str,
        mmproj_path: str,
        host: str = "127.0.0.1",
        port: int = 8080,
        gpu_layers: int = 99,
        ctx_size: int = 8192,
        parallel_slots: int = 1,
        temperature: float = 0.0,
        server_url: str | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        self.llama_cpp_dir = str(llama_cpp_dir or "").strip()
        self.model_path = str(model_path or "").strip()
        self.mmproj_path = str(mmproj_path or "").strip()
        self.gpu_layers = int(gpu_layers)
        self.ctx_size = int(ctx_size)
        self.parallel_slots = max(1, int(parallel_slots))
        self.temperature = float(temperature)
        self.workspace_root = Path(workspace_root).expanduser().resolve() if workspace_root else Path(__file__).resolve().parents[2]

        if server_url:
            parsed = urlparse(str(server_url).strip())
            self.host = parsed.hostname or host
            self.port = int(parsed.port or port)
            self.server_url = f"{parsed.scheme or 'http'}://{self.host}:{self.port}"
        else:
            self.host = str(host or "127.0.0.1").strip() or "127.0.0.1"
            self.port = int(port)
            self.server_url = f"http://{self.host}:{self.port}"

    def build_bat_content(self) -> str:
        binary_path = self.resolve_binary_path(allow_missing=True)
        working_dir = self._resolve_working_dir(binary_path)
        model_path = self._resolve_configured_path(self.model_path) if self.model_path else Path("model.gguf")
        mmproj_path = self._resolve_configured_path(self.mmproj_path) if self.mmproj_path else Path("mmproj.gguf")
        command = [
            str(binary_path),
            "-m",
            str(model_path),
            "--mmproj",
            str(mmproj_path),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "-c",
            str(self.ctx_size),
            "--parallel",
            str(self.parallel_slots),
            "-ngl",
            str(self.gpu_layers),
            "--temp",
            self._format_float(self.temperature),
            "--no-cache-prompt",
            "--cache-ram",
            "0",
            "--no-cache-idle-slots",
        ]

        lines = ["@echo off"]
        if working_dir is not None:
            lines.append(f'cd /d "{working_dir}"')

        for index, token in enumerate(command):
            rendered = subprocess.list2cmdline([token])
            prefix = "call " if index == 0 else "  "
            suffix = " ^" if index < len(command) - 1 else ""
            lines.append(f"{prefix}{rendered}{suffix}")

        lines.extend(
            [
                "echo.",
                "echo Server stopped. Press any key to close this window.",
                "pause >nul",
            ]
        )
        return "\n".join(lines) + "\n"

    def write_run_server_bat(self) -> Path:
        servers_dir = self.workspace_root / "servers"
        servers_dir.mkdir(parents=True, exist_ok=True)
        bat_path = servers_dir / "run_server.bat"
        bat_path.write_text(self.build_bat_content(), encoding="utf-8")
        return bat_path

    def check_health(self) -> tuple[bool, str]:
        endpoints = (
            f"{self.server_url}/health",
            f"{self.server_url}/v1/models",
        )
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=3.0)
            except requests.RequestException:
                continue
            if 200 <= int(response.status_code) < 400:
                return True, f"Local OCR server is reachable at {self.server_url}."
        return False, f"Local OCR server is not reachable at {self.server_url}."

    def open_server_folder(self) -> Path:
        servers_dir = self.workspace_root / "servers"
        servers_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(servers_dir))
        else:
            subprocess.Popen(["xdg-open", str(servers_dir)])
        return servers_dir

    def start_external(self) -> Path:
        bat_path = self.write_run_server_bat()
        if os.name == "nt":
            os.startfile(str(bat_path))
        else:
            subprocess.Popen(["sh", str(bat_path)])
        return bat_path

    def resolve_binary_path(self, allow_missing: bool = False) -> Path:
        search_names = ("llama-server.exe", "llama-server")
        configured_path = self._resolve_configured_path(self.llama_cpp_dir) if self.llama_cpp_dir else None
        if configured_path is not None and configured_path.exists():
            if configured_path.is_file():
                return configured_path.resolve()
            for executable_name in search_names:
                for candidate in (
                    configured_path / executable_name,
                    configured_path / "build" / "bin" / executable_name,
                    configured_path / "build" / "bin" / "Release" / executable_name,
                ):
                    if candidate.exists():
                        return candidate.resolve()

        for executable_name in search_names:
            found = shutil.which(executable_name)
            if found:
                return Path(found).resolve()

        if allow_missing:
            if configured_path is not None and str(configured_path).strip():
                if configured_path.suffix.lower() == ".exe":
                    return configured_path
                return configured_path / ("llama-server.exe" if os.name == "nt" else "llama-server")
            return Path("llama-server.exe" if os.name == "nt" else "llama-server")

        raise FileNotFoundError(
            "Could not find the llama-server binary. Check the llama.cpp folder or executable path."
        )

    def _resolve_working_dir(self, binary_path: Path) -> Path | None:
        configured_path = self._resolve_configured_path(self.llama_cpp_dir) if self.llama_cpp_dir else None
        if configured_path is not None:
            if configured_path.exists() and configured_path.is_dir():
                return configured_path.resolve()
            if configured_path.suffix.lower() == ".exe":
                return configured_path.parent
            if str(configured_path).strip():
                return configured_path
        if binary_path.exists():
            return binary_path.resolve().parent
        return None

    def _format_float(self, value: Any) -> str:
        rendered = f"{float(value):.6f}".rstrip("0").rstrip(".")
        return rendered or "0"

    def _resolve_configured_path(self, raw_path: str | Path) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate
        return (self.workspace_root / candidate).resolve()
