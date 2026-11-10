"""Strip files the reviewer should ignore (e.g. ``uv.lock``) from GitHub MCP results."""

import json
import posixpath
import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import RunContext

# Matched against the basename, so nested paths such as ``pkg/uv.lock`` are covered too.
IGNORED_FILES = ("uv.lock",)

# Standard git header for each file's section in a diff
_DIFF_HEADER = re.compile(r"^diff --git a/(?P<path>.+) b/(?P=path)$", re.MULTILINE)


def is_ignored(path: str) -> bool:
    """Return True if ``path`` points at a file the reviewer should not see."""
    return posixpath.basename(path) in IGNORED_FILES


def filter_diff(diff_text: str) -> str:
    """Drop the blocks of ignored files from a diff text string before the model sees it.

    Each removed block is replaced with a one-liner so the model knows the file
    changed and doesn't report it missing in review.
    """
    headers = list(_DIFF_HEADER.finditer(diff_text))
    if not headers:
        return diff_text

    parts = [diff_text[: headers[0].start()]]
    for header, following in zip(headers, [*headers[1:], None], strict=True):
        block = diff_text[header.start() : following.start() if following else len(diff_text)]
        path = header.group("path")
        if is_ignored(path):
            parts.append(f"[{path} omitted: ignored file]\n")
        else:
            parts.append(block)
    return "".join(parts)


def filter_files(payload: Any) -> Any:
    """Drop ignored files from a ``get_files`` result. Complementary to the filter_diff.

    Accepts a JSON string, a list of file objects, or a dict holding that list under
    ``files``, and returns the same type. Unrecognised payloads are returned unchanged.
    """
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except ValueError:
            return payload
        filtered = filter_files(parsed)
        return payload if filtered is parsed else json.dumps(filtered)

    if isinstance(payload, list):
        if not all(isinstance(item, dict) and isinstance(item.get("filename"), str) for item in payload):
            return payload
        return [item for item in payload if not is_ignored(item["filename"])]

    if isinstance(payload, dict) and isinstance(payload.get("files"), list):
        files = filter_files(payload["files"])
        return payload if files is payload["files"] else {**payload, "files": files}

    return payload


async def filter_tool_call(
    ctx: RunContext[Any],
    call_tool: Callable[..., Awaitable[Any]],
    name: str,
    args: dict[str, Any],
) -> Any:
    """``process_tool_call`` hook that filters ignored files out of PR diffs and file lists."""
    result = await call_tool(name, args)
    if name != "pull_request_read":
        return result

    method = args.get("method")
    if method == "get_diff" and isinstance(result, str):
        return filter_diff(result)
    if method == "get_files":
        return filter_files(result)
    return result
