from setuptools import setup, find_packages

setup(
    name="aura-infra",
    version="0.1.0",
    author="NaniLabs",
    author_email="hello@nanilabs.dev",
    description="Financial infrastructure for AI agents - Stripe for the Agent Economy",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/nanilabs/aura-infra",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ]
    },
    keywords="ai agents payments wallets stripe fintech automation llm",
    project_urls={
        "Documentation": "https://docs.aura.nanilabs.dev",
        "Source": "https://github.com/nanilabs/aura-infra",
        "Bug Tracker": "https://github.com/nanilabs/aura-infra/issues",
    },
)
