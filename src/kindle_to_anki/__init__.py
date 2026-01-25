# Kindle to Anki - Main Package

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("kindle_to_anki")
except PackageNotFoundError:
    __version__ = "dev"
