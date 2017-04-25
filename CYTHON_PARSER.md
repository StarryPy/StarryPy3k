## Information
The Cython parser is a Cython (C-Python fusion language) module for the StarryPy packer parser. 
Since it's compiled, it is significantly faster than the pure Python parser. It is distributed as source
with StarryPy3k and includes a file to compile it quickly. Note that the Cython parser is experimental and
therefore may contain bugs, does not yet do all of the parsing work, and is disabled by default.
## Using the Cython parser
Prerequisites:
- Cython (built against 0.25.2)
- A C compiler

Simply run the following command in StarryPy3k's base directory:

`python build_parser.py build_ext --inplace`

Once the Cython parser has been built (as a `.so` on Linux or a `.pyd` on Windows), it will be used automatically.
