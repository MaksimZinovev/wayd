#!/usr/bin/env python3
"""Post a comment (reply) on a WAYD post.

Subcommand:
  post --post-id N --text T   : emits {ok}
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import shared  # noqa: E402


def cmd_post(args: argparse.Namespace) -> None:
    if not shared.validate_post_id(args.post_id):
        shared.emit_error("Invalid post id.", code="bad_post_id")
        return

    cfg = shared.load_config()
    repo = cfg["repo"]
    max_chars = cfg["limits"]["max_chars"]

    text = args.text.strip()
    if not text:
        shared.emit_error("Empty replies are just silence.", code="empty")
        return
    if len(text) > max_chars:
        shared.emit_error(
            f"Comments have the same {max_chars}-char limit as posts. Trim by {len(text) - max_chars}.",
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
        shared.emit_error(shared.translate_gh_error(e, context="comment"), code="gh_failed")
        return

    shared.emit({"ok": True, "post_id": args.post_id})


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
