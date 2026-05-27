# Architecture

Auto-generated diagrams showing the structure of the HaClient codebase.

The diagrams below are regenerated from source on every documentation build
by an MkDocs ``on_pre_build`` hook (see ``tools/mkdocs_hooks.py``), which
invokes ``tools/generate_diagrams.py``.  That script uses ``pyreverse`` to
extract class and package relationships and renders them to SVG via the
Graphviz ``dot`` binary.

If Graphviz or ``pyreverse`` is not available locally, the hook writes
placeholder SVGs in their place so that ``mkdocs build --strict`` still
succeeds; install the ``docs`` extra and Graphviz to regenerate real
diagrams:

```bash
pip install -e ".[docs]"
# macOS:   brew install graphviz
# Ubuntu:  sudo apt-get install graphviz
python tools/generate_diagrams.py
```

## Class Diagram

![Class Diagram](architecture/classes.svg)

## Package Diagram

![Package Diagram](architecture/packages.svg)
