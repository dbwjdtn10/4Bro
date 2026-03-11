"""Auto-updater: check GitHub Releases and download updates."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from core.version import VERSION

GITHUB_REPO = "dbwjdtn10/4Bro"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse version string like 'v2.1.0' or '2.1.0' into tuple."""
    return tuple(int(x) for x in v.lstrip("v").split("."))


class UpdateChecker(QThread):
    """Background thread to check for updates via GitHub Releases API."""

    update_available = pyqtSignal(str, str, str)  # (latest_version, release_notes, download_url)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)  # error message

    def run(self):
        try:
            req = urllib.request.Request(
                RELEASES_API,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "4Bro"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            if not tag:
                self.no_update.emit()
                return

            latest = _parse_version(tag)
            current = _parse_version(VERSION)

            if latest <= current:
                self.no_update.emit()
                return

            # Find zip asset
            download_url = ""
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    download_url = asset["browser_download_url"]
                    break

            if not download_url:
                self.no_update.emit()
                return

            notes = data.get("body", "") or "업데이트가 있습니다."
            self.update_available.emit(tag, notes, download_url)

        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloader(QThread):
    """Download update zip and prepare replacement script."""

    progress = pyqtSignal(int)  # percentage
    download_finished = pyqtSignal(str)  # path to downloaded zip
    download_failed = pyqtSignal(str)  # error

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "4Bro"},
            )
            resp = urllib.request.urlopen(req, timeout=120)

            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024
            last_percent = -1

            tmp_dir = os.path.join(tempfile.gettempdir(), "4Bro_update")
            os.makedirs(tmp_dir, exist_ok=True)
            zip_path = os.path.join(tmp_dir, "4Bro_update.zip")

            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        percent = int(downloaded / total * 100)
                        if percent != last_percent:
                            self.progress.emit(percent)
                            last_percent = percent
                    else:
                        # No Content-Length: emit MB downloaded as fake progress
                        self.progress.emit(min(downloaded * 100 // (80 * 1024 * 1024), 95))

            self.progress.emit(100)
            self.download_finished.emit(zip_path)

        except Exception as e:
            self.download_failed.emit(str(e))


def get_app_dir() -> str:
    """Get the directory where the exe is located."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def apply_update_and_restart(zip_path: str):
    """Create a batch script to replace files and restart the app."""
    app_dir = get_app_dir()
    exe_path = sys.executable if getattr(sys, "frozen", False) else ""

    bat_path = os.path.join(tempfile.gettempdir(), "4Bro_update.bat")

    extract_dir = os.path.join(tempfile.gettempdir(), "4Bro_extracted")

    bat_content = f'''@echo off
chcp 65001 >nul
echo ============================================
echo   4Bro 업데이트 중...
echo ============================================
echo.

:: Wait for app to close
echo 앱 종료 대기 중...
timeout /t 3 /nobreak >nul

:: Clean previous extraction
if exist "{extract_dir}" rmdir /S /Q "{extract_dir}" 2>nul

:: Extract zip (use tar which is built-in on Win10 1803+)
echo 압축 해제 중...
tar -xf "{zip_path}" -C "{tempfile.gettempdir()}" 2>nul
if %ERRORLEVEL% neq 0 (
    :: Fallback to PowerShell
    powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{extract_dir}' -Force" 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [오류] 압축 해제에 실패했습니다.
        pause
        exit /b 1
    )
)

:: Find extracted folder and copy
if exist "{extract_dir}\\4Bro\\" (
    echo 파일 복사 중...
    xcopy "{extract_dir}\\4Bro\\*" "{app_dir}\\" /E /Y /Q >nul
) else if exist "{tempfile.gettempdir()}\\4Bro\\" (
    echo 파일 복사 중...
    xcopy "{tempfile.gettempdir()}\\4Bro\\*" "{app_dir}\\" /E /Y /Q >nul
    rmdir /S /Q "{tempfile.gettempdir()}\\4Bro" 2>nul
) else (
    echo [오류] 업데이트 파일을 찾을 수 없습니다.
    pause
    exit /b 1
)

:: Cleanup extracted files
rmdir /S /Q "{extract_dir}" 2>nul

:: Delete downloaded zip and its folder
rmdir /S /Q "{os.path.dirname(zip_path)}" 2>nul

echo.
echo ============================================
echo   업데이트 완료!
echo ============================================

:: Restart app
if exist "{exe_path}" (
    echo 앱을 다시 시작합니다...
    timeout /t 2 /nobreak >nul
    start "" "{exe_path}"
)

:: Self-delete this batch file
(goto) 2>nul & del "%~f0"
'''

    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Launch batch script and quit
    os.startfile(bat_path)
    sys.exit(0)
