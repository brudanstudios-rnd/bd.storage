import os
import sys
import compileall

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py


def _compile(root_dir):
    # minify, compile and delete .py files
    for current_dir, _, filenames in os.walk(root_dir):

        for filename in filenames:

            if not filename.endswith(".py"):
                continue

            fullname = os.path.join(current_dir, filename)

            _minify(fullname)

            compileall.compile_file(fullname, force=True)

            os.remove(fullname)


def _minify(input_file):

    from pyminifier import minification

    with open(input_file, "r") as in_file:
        source = in_file.read()

    with open(input_file, "w") as out_file:
        output = minification.remove_comments_and_docstrings(source)
        output = minification.dedent(output)
        output = minification.remove_blank_lines(output)
        output = minification.reduce_operators(output)
        out_file.write(output)


class build_obfuscate(build_py):

    def run(self):

        build_py.run(self)

        lib_dir = os.path.abspath(self.build_lib)

        _compile(lib_dir)


setup(
    name='bd',
    version="v0.0.2",
    description=open("README.md", "r").read(),
    long_description='',
    author='Heorhi Samushyia',
    packages=find_packages("python"),
    setup_requires=["pyminifier==2.1"],
    install_requires=map(lambda x: x.strip(), open("requirements.txt", "r").readlines()),
    zip_safe=False,
    package_dir={"": "python"},
    package_data={'bd.loader': ['hooks/*']},
    cmdclass={
        "build_py": build_obfuscate,
    }
)