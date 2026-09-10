"""Import smoke tests."""

import tomllib
from pathlib import Path

import pydanalock.cloud

PUBLIC_API = {
    "ApiError",
    "AsyncDanalockCloud",
    "AuthError",
    "DanalockCloud",
    "DanalockCloudError",
    "DeviceKey",
    "DeviceNotFoundError",
    "DeviceSummary",
    "FirmwareVersion",
    "MemoryTokenStorage",
    "Permission",
    "TokenData",
    "TokenStorage",
}


def test_package_imports() -> None:
    assert pydanalock.cloud.__version__ == "0.5.1"


def test_public_api_surface() -> None:
    """The package root exports the complete public API (spec 0003)."""
    assert set(pydanalock.cloud.__all__) == PUBLIC_API | {"__version__"}
    for name in PUBLIC_API:
        assert getattr(pydanalock.cloud, name) is not None


def test_version_matches_pyproject() -> None:
    """Distribution and package versions stay in sync (spec 0009 R3)."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    assert version == pydanalock.cloud.__version__


def test_httpx_dependency_floor() -> None:
    """The httpx floor stays Home Assistant compatible (spec 0010 R1)."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as handle:
        dependencies = tomllib.load(handle)["project"]["dependencies"]
    assert "httpx>=0.27" in dependencies
