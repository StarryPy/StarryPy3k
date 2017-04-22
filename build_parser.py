from distutils.core import setup
from Cython.Build import cythonize

setup(
    name = "StarryPy Packet Parser",
    ext_modules = cythonize('_parser.pyx')
)