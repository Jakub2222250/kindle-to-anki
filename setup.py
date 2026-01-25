from setuptools import setup, find_packages

# Read version from package
version = {}
with open("src/kindle_to_anki/__init__.py") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)
            break

setup(
    name="kindle_to_anki",
    version=version.get("__version__", "0.0.0"),
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "customtkinter",
        "google-genai",
        "openai",
        "pycountry",
        "requests",
        "thefuzz",
        "tiktoken",
    ],
)
