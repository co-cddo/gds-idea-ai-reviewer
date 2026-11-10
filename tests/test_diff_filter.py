"""Tests for stripping ignored files (uv.lock) from GitHub MCP results."""

import json

from ai_reviewer.diff_filter import filter_diff, filter_files

FOO_BLOCK = """diff --git a/foo.py b/foo.py
index 111..222 100644
--- a/foo.py
+++ b/foo.py
@@ -1 +1 @@
-old
+new
"""

LOCK_BLOCK = """diff --git a/uv.lock b/uv.lock
index 333..444 100644
--- a/uv.lock
+++ b/uv.lock
@@ -1 +1 @@
-version = 1
+version = 2
"""


def test_diff_drops_uv_lock_keeps_foo_and_leaves_note():
    result = filter_diff(LOCK_BLOCK + FOO_BLOCK)

    assert FOO_BLOCK in result
    assert "version = 2" not in result
    assert "diff --git a/uv.lock" not in result
    assert "[uv.lock omitted: ignored file]" in result


def test_diff_drops_nested_uv_lock():
    nested = LOCK_BLOCK.replace("uv.lock", "sub/pkg/uv.lock")

    result = filter_diff(FOO_BLOCK + nested)

    assert FOO_BLOCK in result
    assert "version = 2" not in result
    assert "[sub/pkg/uv.lock omitted: ignored file]" in result


def test_diff_without_ignored_files_is_unchanged():
    assert filter_diff(FOO_BLOCK) == FOO_BLOCK


def test_files_filtering_for_json_string_list_and_dict():
    files = [{"filename": "uv.lock", "patch": "x"}, {"filename": "pyproject.toml", "patch": "y"}]
    expected = [{"filename": "pyproject.toml", "patch": "y"}]

    assert filter_files(files) == expected
    assert json.loads(filter_files(json.dumps(files))) == expected
    assert filter_files({"files": files, "total": 2}) == {"files": expected, "total": 2}


def test_malformed_payload_is_returned_unchanged():
    for payload in ("not json", '{"unexpected": 1}', [1, 2], [{"name": "uv.lock"}], {"files": "nope"}, None, 42):
        assert filter_files(payload) == payload
