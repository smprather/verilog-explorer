"""Test package.

Exists so tests import as `tests.factories`, which resolves statically and at
run time alike. Relying on pytest's `sys.path` insertion (`from conftest import
…`) works only at run time and is invisible to a language server, which reports
it as an unresolved import on every test file that uses it.
"""
