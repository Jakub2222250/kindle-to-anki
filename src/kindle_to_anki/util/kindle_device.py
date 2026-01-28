"""Cross-platform Kindle device detection and vocab.db copying."""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Common Kindle device name patterns
KINDLE_DEVICE_PATTERNS = [
    "Kindle",
    "Amazon Kindle",
    "Kindle Paperwhite",
    "Kindle Oasis",
    "Kindle Voyage",
    "Kindle Basic",
]

VOCAB_DB_RELATIVE_PATH = Path("system") / "vocabulary" / "vocab.db"


def get_inputs_dir() -> Path:
    """Get the data/inputs directory."""
    from kindle_to_anki.util.paths import get_inputs_dir as _get_inputs_dir
    return _get_inputs_dir()


def find_and_copy_vocab_db() -> Tuple[bool, str]:
    """
    Find connected Kindle and copy vocab.db.
    Returns (success, message).
    """
    system = platform.system()

    if system == "Windows":
        return _copy_vocab_windows()
    elif system == "Darwin":  # macOS
        return _copy_vocab_macos()
    elif system == "Linux":
        return _copy_vocab_linux()
    else:
        return False, f"Unsupported operating system: {system}"


def _copy_vocab_windows() -> Tuple[bool, str]:
    """Copy vocab.db from Kindle on Windows using MTP via PowerShell."""
    inputs_dir = get_inputs_dir()

    # PowerShell script to find Kindle via MTP and copy vocab.db
    ps_script = '''
$s = New-Object -ComObject Shell.Application
$drives = $s.Namespace(17).Items()
$patterns = @("Kindle")
$mtp = $null
foreach ($drive in $drives) {
    if ($drive.IsFolder) {
        foreach ($pattern in $patterns) {
            if ($drive.Name -like "*$pattern*") {
                $mtp = $drive
                break
            }
        }
        if ($mtp) { break }
    }
}
if (-not $mtp) { Write-Error "Kindle not found"; exit 1 }
$root = $mtp.GetFolder
$internal = $root.Items() | Where-Object { $_.Name -eq "Internal Storage" } | Select-Object -First 1
if (-not $internal) { $internal = $root.Items() | Select-Object -First 1 }
$system = $internal.GetFolder.Items() | Where-Object { $_.Name -eq "system" } | Select-Object -First 1
if (-not $system) { Write-Error "system folder not found"; exit 1 }
$voc = $system.GetFolder.Items() | Where-Object { $_.Name -eq "vocabulary" } | Select-Object -First 1
if (-not $voc) { Write-Error "vocabulary folder not found"; exit 1 }
$db = $voc.GetFolder.ParseName("vocab.db")
if (-not $db) { Write-Error "vocab.db not found"; exit 1 }
$tempDir = [System.IO.Path]::GetTempPath()
$s.NameSpace($tempDir).CopyHere($db, 16)
$tempVocab = Join-Path $tempDir "vocab.db"
Move-Item $tempVocab "OUTPUT_PATH" -Force
'''
    output_path = str(inputs_dir / "vocab_powershell_copy.db").replace("\\", "\\\\")
    ps_script = ps_script.replace("OUTPUT_PATH", output_path)

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return True, "Successfully copied vocab.db from Kindle"
        else:
            error = result.stderr.strip() if result.stderr else "Kindle not found or not connected"
            return False, error
    except subprocess.TimeoutExpired:
        return False, "Timeout while copying from Kindle"
    except Exception as e:
        return False, str(e)


def _copy_vocab_macos() -> Tuple[bool, str]:
    """Copy vocab.db from Kindle on macOS (mounted as mass storage)."""
    inputs_dir = get_inputs_dir()

    # On macOS, Kindle mounts under /Volumes
    volumes_path = Path("/Volumes")
    kindle_mount = _find_kindle_mount(volumes_path)

    if not kindle_mount:
        return False, "Kindle not found in /Volumes. Make sure your Kindle is connected and mounted."

    vocab_path = kindle_mount / VOCAB_DB_RELATIVE_PATH
    if not vocab_path.exists():
        return False, f"vocab.db not found at expected location: {vocab_path}"

    try:
        dest_path = inputs_dir / "vocab_copy.db"
        shutil.copy2(vocab_path, dest_path)
        return True, f"Successfully copied vocab.db from {kindle_mount.name}"
    except Exception as e:
        return False, f"Failed to copy vocab.db: {e}"


def _copy_vocab_linux() -> Tuple[bool, str]:
    """Copy vocab.db from Kindle on Linux (mounted as mass storage or MTP)."""
    inputs_dir = get_inputs_dir()

    # Common mount points on Linux
    mount_locations = [
        Path("/media") / (subprocess.getoutput("whoami") or "user"),  # Ubuntu/Debian
        Path("/run/media") / (subprocess.getoutput("whoami") or "user"),  # Fedora/Arch
        Path("/mnt"),
    ]

    # Also check for MTP mounts via gvfs
    gvfs_path = Path.home() / ".gvfs"
    if gvfs_path.exists():
        mount_locations.insert(0, gvfs_path)

    # Check XDG runtime for gvfs mounts (modern systems)
    xdg_runtime = Path(f"/run/user/{subprocess.getoutput('id -u')}/gvfs")
    if xdg_runtime.exists():
        mount_locations.insert(0, xdg_runtime)

    kindle_mount = None
    for base_path in mount_locations:
        if base_path.exists():
            kindle_mount = _find_kindle_mount(base_path)
            if kindle_mount:
                break

    if not kindle_mount:
        return False, "Kindle not found. Make sure your Kindle is connected and mounted."

    vocab_path = kindle_mount / VOCAB_DB_RELATIVE_PATH
    if not vocab_path.exists():
        # For MTP, path structure might be different
        alt_vocab_path = kindle_mount / "Internal Storage" / "system" / "vocabulary" / "vocab.db"
        if alt_vocab_path.exists():
            vocab_path = alt_vocab_path
        else:
            return False, f"vocab.db not found at expected location"

    try:
        dest_path = inputs_dir / "vocab_copy.db"
        shutil.copy2(vocab_path, dest_path)
        return True, f"Successfully copied vocab.db from {kindle_mount.name}"
    except Exception as e:
        return False, f"Failed to copy vocab.db: {e}"


def _find_kindle_mount(base_path: Path) -> Optional[Path]:
    """Find Kindle mount point under the given base path."""
    if not base_path.exists():
        return None

    try:
        for item in base_path.iterdir():
            if not item.is_dir():
                continue
            name_lower = item.name.lower()
            # Check if directory name matches Kindle patterns
            for pattern in KINDLE_DEVICE_PATTERNS:
                if pattern.lower() in name_lower:
                    return item
            # Also check for vocab.db presence as fallback identification
            vocab_check = item / VOCAB_DB_RELATIVE_PATH
            if vocab_check.exists():
                return item
    except PermissionError:
        pass

    return None
