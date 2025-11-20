from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="semantic-code-search",
    version="0.4.0",
    author="Original Author",
    author_email="kiril@codeball.ai",
    description="Search your codebase with natural language",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sturdy-dev/semantic-code-search",
    packages=find_packages(where="src"),  # Look in src directory
    package_dir={"": "src"},              # Map root package to src
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.24.0",
        "prompt_toolkit>=3.0.39",
        "Pygments>=2.15.0",
        "sentence_transformers>=2.2.2",
        "torch>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "sem=semantic_code_search.cli:main",
        ],
    },
)
