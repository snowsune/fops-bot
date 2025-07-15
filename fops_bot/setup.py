#!/usr/bin/env python

from setuptools import setup, find_packages

readme = open("README.md").read()

setup(
    name="fops_bot",
    description="todo",
    author="Furries of SNHU",
    author_email="tbd@gmail.com",
    url="https://github.com/KenwoodFox/FOpS-Bot",
    packages=find_packages(include=["fops_bot"]),
    package_dir={"fops-bot": "fops_bot"},
    entry_points={
        "console_scripts": [
            "fops-bot=fops_bot.__main__:main",
        ],
    },
    python_requires=">=3.10.0",
    version="0.0.0",
    long_description=readme,
    include_package_data=True,
    install_requires=[
        "discord.py",
    ],
    license="MIT",
)
