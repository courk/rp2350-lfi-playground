#!/usr/bin/env python3
"""Simple system monitoring utils."""
import re
from asyncio import subprocess


class SystemUtilsError(Exception):
    """Raised in case of an error when getting the CPU temperature."""

    pass


async def get_cpu_temp() -> float:
    """Get the CPU temperature, expressed in °C."""
    try:
        p = await subprocess.create_subprocess_exec(
            "vcgencmd", "measure_temp", stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
    except FileNotFoundError:
        raise SystemUtilsError("vcgencmd cannot be found")

    raw_stdout, raw_stderr = await p.communicate()

    if p.returncode != 0:
        raise SystemUtilsError(f'vcgencmd error: {raw_stderr.decode(errors="replace")}')

    stdout = raw_stdout.decode(errors="replace").strip()

    match = re.match(r"^temp=(\d+\.\d+)'C$", stdout)

    if match is None:
        raise SystemUtilsError(f"Cannot parse vcgencmd output: {stdout}")

    return float(match.group(1))


def _get_version_string_from_file() -> str:
    """Get the version of the LFI playground assuming a no-git deployment."""
    try:
        with open(".version", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Unknown version"


async def get_version_string() -> str:
    """Return the version of the LFI playground."""
    try:
        p = await subprocess.create_subprocess_exec(
            "git", "describe", "--tags", stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
    except FileNotFoundError:
        return _get_version_string_from_file()

    raw_stdout, _ = await p.communicate()

    if p.returncode != 0:
        return _get_version_string_from_file()

    return raw_stdout.decode(errors="replace")
