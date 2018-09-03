import os
import sys

from setuptools import setup, find_packages

requirements = [
    "metayaml==0.22",
    "pluginbase==0.7",
    "requests==2.19.1",
    "pathlib2==2.3.2",
    "pyside2"
]

if "BD_DEVEL" in os.environ:
    requirements.extend([
        "pyminifier==2.1",
        "GitPython==2.1.10"
    ])

setup(
    name='bd',
    version="v0.0.12",
    description="The main bd api library",
    long_description='',
    author='Heorhi Samushyia',
    packages=find_packages("python"),
    install_requires=requirements,
    dependency_links=[
        'http://download.qt.io/snapshots/ci/pyside/5.11/latest/pyside2'
    ],
    zip_safe=False,
    package_dir={"": "python"},
    package_data={'bd.loader': ['hooks/*']},
)