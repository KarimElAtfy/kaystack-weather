"""Blob storage for the lake and the public container, or a local folder for dry runs.

Raw objects are written once. A second write to the same name is refused by the
service (If-None-Match: *), and for radar frames, MOSMIX issues and model runs,
whose names carry the source's own time, that refusal is the deduplication.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath


def raw_name(source: str, when: datetime, variant: str, ext: str) -> str:
    return f"{source}/{when:%Y/%m/%d}/{when:%Y%m%dT%H%M%SZ}-{variant}.{ext}"


def name_time(name: str) -> datetime:
    stamp = PurePosixPath(name).name.split("-", 1)[0]
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def day_prefix(source: str, day: date) -> str:
    return f"{source}/{day:%Y/%m/%d}/"


class AzureStore:
    def __init__(self, account: str, credential) -> None:
        from azure.storage.blob import BlobServiceClient

        self._service = BlobServiceClient(
            f"https://{account}.blob.core.windows.net", credential=credential
        )

    def put_new(
        self,
        container: str,
        name: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> bool:
        """False when the object exists already."""
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings

        blob = self._service.get_blob_client(container, name)
        try:
            # overwrite=False is what makes the SDK send If-None-Match: *
            blob.upload_blob(
                data,
                overwrite=False,
                metadata=metadata,
                content_settings=ContentSettings(content_type=content_type),
            )
        except ResourceExistsError:
            return False
        return True

    def put(self, container: str, name: str, data: bytes, content_type: str) -> None:
        from azure.storage.blob import ContentSettings

        self._service.get_blob_client(container, name).upload_blob(
            data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
        )

    def exists(self, container: str, name: str) -> bool:
        return self._service.get_blob_client(container, name).exists()

    def read(self, container: str, name: str) -> tuple[bytes, dict[str, str]]:
        download = self._service.get_blob_client(container, name).download_blob()
        return download.readall(), dict(download.properties.metadata)

    def names(self, container: str, prefix: str) -> list[str]:
        client = self._service.get_container_client(container)
        return sorted(client.list_blob_names(name_starts_with=prefix))

    def read_versioned(self, container: str, name: str) -> tuple[bytes | None, str | None]:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            download = self._service.get_blob_client(container, name).download_blob()
        except ResourceNotFoundError:
            return None, None
        return download.readall(), download.properties.etag

    def swap(
        self,
        container: str,
        name: str,
        data: bytes,
        etag: str | None,
        content_type: str,
        cache_control: str,
    ) -> bool:
        """Replaces the object only if nobody wrote it since it was read as `etag`."""
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
        from azure.storage.blob import ContentSettings

        settings = ContentSettings(content_type=content_type, cache_control=cache_control)
        blob = self._service.get_blob_client(container, name)
        try:
            if etag is None:
                blob.upload_blob(data, overwrite=False, content_settings=settings)
            else:
                blob.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=settings,
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
        except (ResourceExistsError, ResourceModifiedError):
            return False
        return True


class FolderStore:
    """The same calls on a local folder: one subfolder per container, and the blob
    metadata as JSON in a parallel `<container>.meta` folder."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, container: str, name: str) -> Path:
        return self.root / container / name

    def put_new(
        self,
        container: str,
        name: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> bool:
        path = self._path(container, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as f:
                f.write(data)
        except FileExistsError:
            return False
        if metadata:
            meta = self.root / f"{container}.meta" / f"{name}.json"
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps(metadata), encoding="utf-8")
        return True

    def put(self, container: str, name: str, data: bytes, content_type: str) -> None:
        path = self._path(container, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def exists(self, container: str, name: str) -> bool:
        return self._path(container, name).is_file()

    def read(self, container: str, name: str) -> tuple[bytes, dict[str, str]]:
        meta = self.root / f"{container}.meta" / f"{name}.json"
        metadata = json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}
        return self._path(container, name).read_bytes(), metadata

    def names(self, container: str, prefix: str) -> list[str]:
        base = self.root / container
        folder = base / prefix.rpartition("/")[0]
        if not folder.is_dir():
            return []
        found = (p.relative_to(base).as_posix() for p in folder.rglob("*") if p.is_file())
        return sorted(n for n in found if n.startswith(prefix))

    def read_versioned(self, container: str, name: str) -> tuple[bytes | None, str | None]:
        path = self._path(container, name)
        if not path.is_file():
            return None, None
        data = path.read_bytes()
        # The content stands in for the ETag: two quick writes can leave the same
        # modification time.
        return data, hashlib.sha256(data).hexdigest()

    def swap(
        self,
        container: str,
        name: str,
        data: bytes,
        etag: str | None,
        content_type: str,
        cache_control: str,
    ) -> bool:
        path = self._path(container, name)
        _, current = self.read_versioned(container, name)
        if current != etag:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True


type Store = AzureStore | FolderStore
