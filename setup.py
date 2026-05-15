from setuptools import find_packages, setup

setup(
    name="interviewforge",
    version="0.1.0",
    description="Local-first interview recording review reports with a Codex skill and CLI.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="K1XE",
    license="MIT",
    python_requires=">=3.9",
    packages=find_packages(include=["interviewforge", "interviewforge.*"]),
    include_package_data=True,
    entry_points={"console_scripts": ["interviewforge=interviewforge.cli:main"]},
)
