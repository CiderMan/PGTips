# PGTips

Photograph geotagger: a wxPython (Phoenix, 4.x) GUI that imports, losslessly rotates, geotags
and files photos. Shells out to `exiftool`, and optionally `jpegtran`.

## Python

- Python 3.12 is the minimum supported version. Don't add Python 2 compatibility shims
  (`six`, `__future__`, etc.).
- Run the app from anywhere with `python3 pgtips.py`.
- Use `pathlib.Path` for file system paths and operations, not `os.path` (e.g. `Path.walk()`
  rather than `os.walk()`, `path.suffix` rather than `os.path.splitext()`).

## Layout

- `pgtips.py` - main frame and worker threads. Importable (startup is in `main()`), so it can be
  tested.
- `slippy/` - the slippy-map panel package (tiles, cache, markers, tracks, regions).
- `sub-modules/` - plain modules put on `sys.path` by `pgtips.py` (GPS file parsing,
  exiftool wrapper, file finding, image list, options dialog, embedded images).

## Tests

- Use the standard library `unittest` module, not pytest.
- Tests live in the top-level `test/` directory, which mirrors the layout of the code under
  test, e.g. `slippy/regions.py` -> `test/slippy/test_regions.py` and
  `sub-modules/gpsfiles.py` -> `test/sub-modules/test_gpsfiles.py`.
- Run them all from the repo root with `python3 -m unittest`.

## Formatting

- Format Python code with `black -l 99`.

## Linting

- Lint with `pylint pgtips.py slippy sub-modules test`, run from the repo root (`.pylintrc` adds
  `sub-modules/` to the path relative to the current directory). Keep it at 10/10.
- `.pylintrc` turns off checks that don't fit the codebase's conventions (camelCase and wx-style
  names, docstrings everywhere, `%`-formatting, etc.). Fix other messages rather than
  disabling them; if a disable is really needed, make it inline with a comment saying why.
