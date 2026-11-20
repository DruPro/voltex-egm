"""Compiles the voltex2 engine into the package (egm/_bin/voltex2) during `pip install`.

Needs a C++17 compiler: $CXX, else c++ / g++ / clang++. Set EGM_SKIP_ENGINE_BUILD=1 to skip
(then point VOLTEX at a binary, or put voltex2 on PATH).
"""
import os
import shutil
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution

HERE = os.path.dirname(os.path.abspath(__file__))


class BuildEngine(build_py):
    def run(self):
        super().run()
        if os.environ.get("EGM_SKIP_ENGINE_BUILD") == "1":
            return
        cxx = os.environ.get("CXX") or next((c for c in ("c++", "g++", "clang++") if shutil.which(c)), None)
        if not cxx:
            raise SystemExit("egm: no C++17 compiler found (set CXX, or EGM_SKIP_ENGINE_BUILD=1 and provide voltex2)")
        out_dir = os.path.join(self.build_lib, "egm", "_bin")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "voltex2")
        cmd = [cxx, "-O2", "-std=c++17", "-o", out, os.path.join(HERE, "src", "voltex2.cpp")]
        print("egm: building engine:", " ".join(cmd))
        subprocess.check_call(cmd)


class BinaryDistribution(Distribution):
    """The wheel carries a compiled binary, so tag it for this platform."""
    def has_ext_modules(self):
        return True


setup(cmdclass={"build_py": BuildEngine}, distclass=BinaryDistribution)
