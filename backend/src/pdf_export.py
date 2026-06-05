"""DOCX → PDF via headless LibreOffice (template-faithful).

Windows path C:\\Program Files\\LibreOffice\\program\\soffice.exe is auto-detected.
Falls back to docx2pdf on Windows if LibreOffice is unavailable.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

# Known Windows install path — checked as last resort if shutil.which fails
_WIN_SOFFICE = Path("C:/Program Files/LibreOffice/program/soffice.exe")


def _find_soffice() -> str | None:
    """Locate the soffice binary, checking config, PATH, and Windows default."""
    # 1. Config-supplied value (may already be the full path)
    if config.LIBREOFFICE_BIN and Path(config.LIBREOFFICE_BIN).exists():
        return config.LIBREOFFICE_BIN
    # 2. shutil.which (works if the directory is on PATH)
    for name in (config.LIBREOFFICE_BIN, "soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    # 3. Windows standard install path
    if _WIN_SOFFICE.exists():
        return str(_WIN_SOFFICE)
    return None


def docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    docx_path = Path(docx_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / (docx_path.stem + ".pdf")

    soffice = _find_soffice()
    if soffice:
        # Use a temp user-installation dir so concurrent conversions don't
        # collide on the LibreOffice lock file (~/.config/libreoffice).
        with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile_dir:
            profile_url = Path(profile_dir).as_uri()
            cmd = [
                soffice,
                f"-env:UserInstallation={profile_url}",
                "--headless",
                "--norestore",
                "--nofirststartwizard",
                "--convert-to", "pdf",
                "--outdir", str(out_dir),
                str(docx_path),
            ]
            log.info("LibreOffice cmd: %s", " ".join(cmd))
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                log.debug("soffice stdout: %s", result.stdout.decode(errors="ignore"))
                if target.exists():
                    return target
                log.warning("soffice exited OK but PDF not found at %s", target)
            except subprocess.CalledProcessError as e:
                log.warning(
                    "LibreOffice conversion failed (rc=%d): %s",
                    e.returncode,
                    e.stderr.decode(errors="ignore"),
                )
            except subprocess.TimeoutExpired:
                log.warning("LibreOffice conversion timed out after 120s")
            except Exception as e:
                log.warning("LibreOffice exec error: %s", e)
    else:
        log.warning(
            "soffice not found via config (%s), PATH, or default Windows path. "
            "Ensure LIBREOFFICE_BIN is set correctly in .env.",
            config.LIBREOFFICE_BIN,
        )

    # Windows fallback via docx2pdf (requires Microsoft Word)
    try:
        from docx2pdf import convert  # type: ignore
        log.info("Falling back to docx2pdf")
        convert(str(docx_path), str(target))
        if target.exists():
            return target
    except Exception as e:
        log.warning("docx2pdf fallback failed: %s", e)

    raise RuntimeError(
        f"PDF conversion failed. "
        f"LibreOffice binary: {soffice or 'NOT FOUND'}. "
        "Set LIBREOFFICE_BIN=C:\\Program Files\\LibreOffice\\program\\soffice.exe in backend/.env"
    )
