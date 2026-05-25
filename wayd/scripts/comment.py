#!/usr/bin/env python3
"""Post a comment (reply) on a WAYD post.

Subcommand:
  post --post-id N --text T    — emits {ok}
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import shared  # noqa: E402


def cmd_post(args: argparse.Namespace) -> None:
    cfg = shared.load_config()
    repo = cfg["repo"]
    max_chars = cfg["limits"]["max_chars"]

    text = args.text.strip()
    if not text:
        shared.emit_error("Empty replies are just silence.", code="empty")
        return
    if len(text) > max_chars:
        shared.emit_error(
            f"Too long by {len(text) - max_chars} chars. Trim it down.",
            code="too_long",
        )
        return

    try:
        shared.gh(
            [
                "issue", "comment", str(args.post_id),
                "--repo", repo,
                "--body", text,
            ]
        )
    except shared.GhError as e:
        shared.log_error(f"comment failed: {e}")
        shared.emit_error(_translate_gh_error(e), code="gh_failed")
        return

    shared.emit({"ok": True, "post_id": args.post_id})


def _translate_gh_error(e: shared.GhError) -> str:
    s = (e.stderr or "").lower()
    if "404" in s or "not found" in s:
        return "That post isn't there anymore. Maybe the author deleted it."
    if "423" in s or "locked" in s:
        return "This thread has been locked — probably because the post was deleted."
    if "403" in s or "permission" in s or "forbidden" in s:
        return "GitHub says you can't reply here right now."
    if "could not resolve host" in s or "network" in s or e.returncode == 127:
        return "Couldn't reach GitHub right now. Check your connection."
    return "Couldn't post your reply. Try again in a moment."


def main() -> None:
    parser = argparse.ArgumentParser(prog="comment")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_post = sub.add_parser("post")
    p_post.add_argument("--post-id", type=int, required=True)
    p_post.add_argument("--text", required=True)
    p_post.set_defaults(func=cmd_post)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
