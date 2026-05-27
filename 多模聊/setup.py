from setuptools import setup, find_packages

setup(
    name="duomoliao",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["chat"],
    install_requires=[
        "openai>=1.0.0",
        "anthropic>=0.30.0",
        "google-genai>=1.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "duomoliao=chat:main",
        ],
    },
)
