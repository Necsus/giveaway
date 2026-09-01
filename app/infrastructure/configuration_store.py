import os
import shutil
from pathlib import Path

from app.core.configuration import ApplicationConfiguration


class ConfigurationStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ApplicationConfiguration | None:
        try:
            content = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        return ApplicationConfiguration.model_validate_json(content)

    def save(self, configuration: ApplicationConfiguration) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = self._path.with_name(f"{self._path.name}.tmp")
        backup_path = self._path.with_name(f"{self._path.name}.bak")
        content = f"{configuration.model_dump_json(indent=2)}\n"

        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                os.fchmod(file.fileno(), 0o600)
                _ = file.write(content)
                file.flush()
                os.fsync(file.fileno())

            if self._path.exists():
                shutil.copy2(self._path, backup_path)
                backup_path.chmod(0o600)

            os.replace(temporary_path, self._path)
            self._path.chmod(0o600)
        finally:
            temporary_path.unlink(missing_ok=True)
