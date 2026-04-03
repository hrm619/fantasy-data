from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    __version__ = _pkg_version("fantasy-data")
except PackageNotFoundError:
    __version__ = "0.1.0"
