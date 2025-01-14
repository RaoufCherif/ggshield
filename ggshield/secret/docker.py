import json
import os.path
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from click import UsageError
from pygitguardian import GGClient

from ggshield.core.cache import Cache
from ggshield.core.dirs import get_cache_dir
from ggshield.core.errors import UnexpectedError
from ggshield.core.file_utils import is_path_binary
from ggshield.core.text_utils import display_heading, display_info
from ggshield.core.types import IgnoredMatch
from ggshield.scan import Files, ScanContext, Scannable, StringScannable
from ggshield.scan.id_cache import IDCache

from .rich_secret_scanner_ui import RichSecretScannerUI
from .secret_scan_collection import SecretScanCollection
from .secret_scanner import SecretScanner


FILEPATH_BANLIST = [
    r"^/?usr/(?!share/nginx)",
    r"^/?lib/",
    r"^/?share/",
    r"^/?bin/",
    r"^/?sbin/",
    r"^/?node_modules/",
    r"^/?include/",
    r"^/?vendor/",
    r"^/?texlive/",
    r"^/?var/",
    r"^/?fonts/",
    r"^/?npm/",
    r"^/?site-packages/",
]
FILEPATH_BANLIST_PATTERNS = {
    re.compile(banned_filepath) for banned_filepath in FILEPATH_BANLIST
}

LAYER_TO_SCAN_PATTERN = re.compile(r"\b(copy|add)\b", re.IGNORECASE)

TAG_PATTERN = re.compile(r":[a-zA-Z0-9_][-.a-zA-Z0-9_]{0,127}$")


class InvalidDockerArchiveException(Exception):
    pass


class DockerContentScannable(Scannable):
    """
    A Scannable for a file inside a Docker image
    """

    def __init__(
        self, layer_id: str, tar_file: tarfile.TarFile, tar_info: tarfile.TarInfo
    ):
        super().__init__()
        self._layer_id = layer_id
        self._tar_file = tar_file
        self._tar_info = tar_info
        self._content: Optional[str] = None

    @property
    def url(self) -> str:
        return f"{self._layer_id}:/{self._tar_info.name}"

    @property
    def filename(self) -> str:
        return self.url

    @property
    def path(self) -> Path:
        return Path("/", self._tar_info.name)

    def is_longer_than(self, size: int) -> bool:
        if self._content:
            # We already have the content, easy
            return len(self._content) > size

        if self._tar_info.size < size:
            # Shortcut: if the byte size is smaller than `size`, we can be sure the
            # decoded size will be smaller
            return False

        # We need to decode at least the beginning of the file to determine if it's
        # small enough
        fp = self._tar_file.extractfile(self._tar_info)
        assert fp is not None
        with fp:
            result, self._content = Scannable._is_file_longer_than(
                fp, size  # type:ignore
            )
            # mypy complains that fp is IO[bytes] but _is_file_longer_than() expects
            # BinaryIO. They are compatible, ignore the error.
        return result

    @property
    def content(self) -> str:
        if self._content is None:
            file = self._tar_file.extractfile(self._tar_info)
            assert file is not None
            byte_content = file.read()
            self._content = Scannable._decode_bytes(byte_content)
        return self._content


@dataclass
class LayerInfo:
    filename: str
    command: str
    diff_id: str

    def should_scan(self) -> bool:
        """
        Returns True if a layer should be scanned, False otherwise.
        Only COPY and ADD layers should be scanned.
        """
        if self.command == "":
            # Some images contain layers with no commands. Since we don't know how they have
            # been created, we must scan them.
            # Examples of such images from Docker Hub:
            # - aevea/release-notary:0.9.7
            # - redhat/ubi8:8.6-754
            return True
        else:
            return LAYER_TO_SCAN_PATTERN.search(self.command) is not None


class DockerImage:
    # The manifest.json file
    manifest: Dict[str, Any]

    # The Image JSON file
    # (see https://github.com/moby/moby/blob/master/image/spec/v1.2.md#terminology)
    image: Dict[str, Any]

    layer_infos: List[LayerInfo]

    def __init__(self, tar_file: tarfile.TarFile):
        self.tar_file = tar_file
        self._load_manifest()

        self._load_image()

        self.config_scannable = StringScannable(
            "Dockerfile or build-args", json.dumps(self.image, indent=2)
        )

        self._load_layer_infos()

    def get_layer(self, layer_info: LayerInfo) -> Files:
        scannables = list(self._get_layer_scannables(layer_info))
        return Files(scannables)

    def _load_manifest(self) -> None:
        """
        Reads "manifest.json", stores result in self.manifest
        """
        manifest_file = self.tar_file.extractfile("manifest.json")
        if manifest_file is None:
            raise InvalidDockerArchiveException("No manifest file found.")

        self.manifest = json.load(manifest_file)[0]

    def _load_image(self) -> None:
        """
        Reads the image JSON file, stores result in self.image
        """
        try:
            config_file_path = self.manifest["Config"]
        except KeyError:
            raise InvalidDockerArchiveException("No Config key in manifest.")

        config_file_info = self.tar_file.getmember(config_file_path)
        if config_file_info is None:
            raise InvalidDockerArchiveException("No config file found.")

        config_file = self.tar_file.extractfile(config_file_info)
        if config_file is None:
            raise InvalidDockerArchiveException("Config file could not be extracted.")

        self.image = json.load(config_file)

    def _load_layer_infos(self) -> None:
        """
        Fill self.layer_infos with LayerInfo instances for all non-empty layers
        """

        #
        # manifest["Layers"] contains a list of non-empty layers like this:
        #
        #   "<random_id>/layer.tar"
        layer_filenames = self.manifest["Layers"]

        # image["history"] contains a list of entries like this:
        # {
        #   "created": ISO8601 timestamp,
        #   "created_by": command to build the layer
        #   "empty_layer": if present, equals true
        # }
        non_empty_history_entries = [
            x for x in self.image["history"] if not x.get("empty_layer")
        ]

        #
        # image["rootfs"]["diff_ids"] contains the list of layer IDs
        diff_ids = self.image["rootfs"]["diff_ids"]

        layer_infos = [
            LayerInfo(
                filename=filename,
                command=history.get("created_by", ""),
                diff_id=diff_id,
            )
            for filename, history, diff_id in zip(
                layer_filenames, non_empty_history_entries, diff_ids
            )
        ]
        self.layer_infos = [x for x in layer_infos if x.should_scan()]

    def _get_layer_scannables(self, layer_info: LayerInfo) -> Iterable[Scannable]:
        """
        Extracts Scannable to be scanned for given layer.
        """
        layer_filename = layer_info.filename
        layer_archive = tarfile.TarFile(
            name=os.path.join(self.tar_file.name, layer_filename),  # type: ignore
            fileobj=self.tar_file.extractfile(layer_filename),
        )

        layer_id = layer_info.diff_id

        for file_info in layer_archive:
            if not file_info.isfile():
                continue

            if file_info.size == 0:
                continue

            if not _validate_filepath(filepath=file_info.path):
                continue

            yield DockerContentScannable(layer_id, layer_archive, file_info)


def _validate_filepath(
    filepath: str,
) -> bool:
    if any(
        banned_pattern.search(filepath) for banned_pattern in FILEPATH_BANLIST_PATTERNS
    ):
        return False

    if is_path_binary(filepath):
        return False
    return True


def _get_layer_id_cache(secrets_engine_version: str) -> IDCache:
    cache_path = Path(get_cache_dir()) / "docker" / f"{secrets_engine_version}.json"
    return IDCache(cache_path)


def docker_pull_image(image_name: str, timeout: int) -> None:
    """
    Pull docker image and raise exception on timeout or failed to find image

    Timeout after `timeout` seconds.
    """
    command = ["docker", "pull", image_name]
    try:
        subprocess.run(
            command,
            check=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError:
        raise UsageError(f'Image "{image_name}" not found')
    except subprocess.TimeoutExpired:
        raise UnexpectedError('Command "{}" timed out'.format(" ".join(command)))


def docker_save_to_tmp(image_name: str, destination_path: Path, timeout: int) -> None:
    """
    Do a `docker save <image_name> -o <destination_path>`

    Limit docker commands to run at most `timeout` seconds.
    """
    image_name = (
        image_name if TAG_PATTERN.search(image_name) else image_name + ":latest"
    )
    command = ["docker", "save", image_name, "-o", str(destination_path)]

    try:
        display_info("Saving docker image... ", nl=False)
        subprocess.run(
            command,
            check=True,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        display_info("OK")
    except subprocess.CalledProcessError as exc:
        err_string = str(exc.stderr)
        if "No such image" in err_string or "reference does not exist" in err_string:
            display_info("need to download image first")
            docker_pull_image(image_name, timeout)

            docker_save_to_tmp(image_name, destination_path, timeout)
        else:
            raise UnexpectedError(
                f"Unable to save docker archive:\nError: {err_string}"
            )
    except subprocess.TimeoutExpired:
        raise UnexpectedError('Command "{}" timed out'.format(" ".join(command)))


def docker_scan_archive(
    archive_path: Path,
    client: GGClient,
    cache: Cache,
    matches_ignore: Iterable[IgnoredMatch],
    scan_context: ScanContext,
    ignored_detectors: Optional[Set[str]] = None,
) -> SecretScanCollection:

    scanner = SecretScanner(
        client=client,
        cache=cache,
        scan_context=scan_context,
        ignored_matches=matches_ignore,
        ignored_detectors=ignored_detectors,
    )
    secrets_engine_version = client.secrets_engine_version
    assert secrets_engine_version is not None
    layer_id_cache = _get_layer_id_cache(secrets_engine_version)

    with tarfile.open(archive_path) as archive:
        docker_image = DockerImage(archive)

        display_heading("Scanning Docker config")
        with RichSecretScannerUI(1) as ui:
            results = scanner.scan(
                [docker_image.config_scannable],
                scanner_ui=ui,
            )

        for info in docker_image.layer_infos:
            layer = docker_image.get_layer(info)
            file_count = len(layer.files)
            if file_count == 0:
                continue
            print()
            layer_id = info.diff_id
            if layer_id in layer_id_cache:
                display_heading(f"Skipping layer {layer_id}: already scanned")
            else:
                display_heading(f"Scanning layer {info.diff_id}")
                with RichSecretScannerUI(file_count) as ui:
                    layer_results = scanner.scan(layer.files, scanner_ui=ui)
                if not layer_results.has_policy_breaks:
                    layer_id_cache.add(layer_id)
                results.extend(layer_results)

    return SecretScanCollection(
        id=str(archive), type="scan_docker_archive", results=results
    )
