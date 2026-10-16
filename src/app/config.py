# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Configuration and preset management adhering to XDG specs and security guidelines."""

import os
import sys
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field, ValidationError

APP_NAME = "jgobdii-reader"


class ToolPreset(BaseModel):
    """Schema-validated preset definition model."""

    name: str = Field(default="default", description="Preset name")
    theme: str = Field(default="auto", description="UI theme: 'auto', 'light', or 'dark'")
    max_items: int = Field(default=50, ge=1, le=1000, description="Maximum items to display")
    enable_cache: bool = Field(default=True, description="Enable local temporary caching")
    adapter_type: str = Field(default="elm327", description="Hardware interface: 'elm327', 'j2534', or 'mock'")
    adapter_host: str = Field(default="192.168.0.10", description="ELM327 Wi-Fi host IP or hostname")
    adapter_port: int = Field(default=35000, ge=1, le=65535, description="ELM327 Wi-Fi TCP port")
    vehicle_domain: str = Field(default="car", description="Vehicle domain: car, truck, motorcycle, boat, atv")
    manufacturer: str = Field(default="generic", description="Target manufacturer: toyota, honda, gm, ford, generic")
    vss_pulses_per_mile: int = Field(default=4000, description="Speed sensor pulses per mile for derived Hz")
    poll_interval_ms: int = Field(default=200, ge=20, le=5000, description="Telemetry polling interval in milliseconds")


class AppConfig(BaseModel):
    """Global application configuration model."""

    version: int = Field(default=1, description="Configuration schema version")
    default_preset: str = Field(default="default", description="Active preset name")
    preset: ToolPreset = Field(default_factory=ToolPreset)


def sanitize_log_path(path: str) -> str:
    """Scrub local username and home directory from log strings to protect privacy.

    Args:
        path: Raw filesystem path string to sanitize.

    Returns:
        Sanitized path with the user's home directory replaced by '~<USER>'.
    """
    home_dir = str(Path.home())
    if home_dir and path.startswith(home_dir):
        return path.replace(home_dir, "~<USER>", 1)
    return path


def get_config_dir() -> Path:
    """Return the platform-appropriate configuration directory (XDG compliant).

    Creates the directory with mode 0700 if it does not already exist.

    Returns:
        Absolute Path pointing to the application configuration directory.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        config_root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        config_root = Path(base) if base else Path.home() / ".config"

    target_dir = config_root / APP_NAME
    # SECURITY: Enforce POSIX mode 0700 (rwx------) to restrict multi-user local access
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            try:
                os.chmod(target_dir, 0o700)
            except OSError:
                pass
    return target_dir


def get_presets_dir() -> Path:
    """Return the presets subfolder within the application configuration directory.

    Creates the presets directory with mode 0700 if it does not already exist.

    Returns:
        Absolute Path pointing to the presets directory.
    """
    presets_dir = get_config_dir() / "presets"
    if not presets_dir.exists():
        presets_dir.mkdir(parents=True, exist_ok=True)
        # SECURITY: Maintain mode 0700 permissions on all config subdirectories
        if sys.platform != "win32":
            try:
                os.chmod(presets_dir, 0o700)
            except OSError:
                pass
    return presets_dir


def safe_resolve_preset_path(preset_name: str) -> Path:
    """Safely resolve a preset file path, preventing directory traversal attacks (CWE-22).

    Args:
        preset_name: Name of the preset (with or without '.yaml' extension).

    Returns:
        Canonical absolute Path to the resolved preset file within the presets directory.

    Raises:
        PermissionError: If the resolved path attempts to escape the allowed presets directory.
    """
    clean_name = preset_name.strip()
    if not clean_name.endswith(".yaml"):
        clean_name += ".yaml"

    base_dir = get_presets_dir().resolve()
    target_path = (base_dir / clean_name).resolve()

    # SECURITY: Verify the target path stays strictly inside the designated presets root
    try:
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise PermissionError(f"Access denied: Preset '{preset_name}' escapes allowed directory") from exc

    return target_path


def load_preset(preset_name: str = "default") -> ToolPreset:
    """Load and validate a YAML preset file using safe deserialization (CWE-502).

    If the requested preset file does not exist, a default preset is generated,
    saved with secure permissions, and returned.

    Args:
        preset_name: Identifier of the preset to load. Defaults to 'default'.

    Returns:
        Validated ToolPreset model instance.

    Raises:
        ValueError: If YAML parsing fails or the file content fails schema validation.
    """
    preset_path = safe_resolve_preset_path(preset_name)

    if not preset_path.exists():
        # Create and persist default preset if missing
        default_preset = ToolPreset(name=preset_name)
        save_preset(default_preset)
        return default_preset

    try:
        with open(preset_path, "r", encoding="utf-8") as f:
            # SECURITY: Strictly use safe_load to prevent arbitrary code execution (CWE-502)
            raw_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in preset '{preset_name}': {exc}") from exc

    try:
        return ToolPreset.model_validate(raw_data)
    except ValidationError as exc:
        raise ValueError(f"Invalid preset schema in '{preset_name}': {exc}") from exc


def save_preset(preset: ToolPreset) -> Path:
    """Save a preset to disk with secure POSIX permissions (mode 0600).

    Args:
        preset: Validated ToolPreset instance to persist.

    Returns:
        Absolute Path of the written preset YAML file.
    """
    preset_path = safe_resolve_preset_path(preset.name)
    data = preset.model_dump()

    # Convert to commented YAML representation adhering to open-source preset guidelines
    yaml_content = (
        f"# Preset: {preset.name}\n"
        f"# Auto-generated configuration file adhering to open-source standards.\n"
        + yaml.dump(data, sort_keys=False)
    )

    # SECURITY: Write with mode 0600 (rw-------) so other local users cannot read settings
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600

    fd = os.open(str(preset_path), flags, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return preset_path


def list_presets() -> List[str]:
    """Return a sorted list of all locally available preset identifiers.

    Returns:
        List of preset names discovered in the user's presets directory.
    """
    presets_dir = get_presets_dir()
    presets = {p.stem for p in presets_dir.glob("*.yaml")} | {p.stem for p in presets_dir.glob("*.yml")}
    if not presets:
        load_preset("default")
        return ["default"]
    return sorted(presets)


def reset_all_configuration() -> None:
    """Purge all user-saved presets and restore factory defaults."""
    config_dir = get_config_dir()
    if config_dir.exists():
        for root, dirs, files in os.walk(config_dir, topdown=False):
            for file in files:
                (Path(root) / file).unlink(missing_ok=True)
            for d in dirs:
                (Path(root) / d).rmdir()
    # Reinitialize factory default preset
    load_preset("default")

