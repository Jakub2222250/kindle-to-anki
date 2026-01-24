from setuptools import setup, find_packages

setup(
    name="kindle_to_anki",
    version="0.1.0",
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
