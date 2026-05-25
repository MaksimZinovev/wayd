#!/usr/bin/env python3
"""Fetch and shuffle the WAYD scroll feed.

Subcommands:
  fetch [--vibe S] [--limit N]  : emits {ok, posts: [...]}
  thread --post-id N            : emits {ok, post, comments: [...]}

The caller (Claude, orchestrating SKILL.md) is responsible for the random
selection and the "recently_seen" exclusion. We return the candidate pool,
already filtered to exclude soft-deleted posts and posts from blocked users.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import shared  # noqa: E402


def cmd_fetch(args: argparse.Namespace) -> None:
    cfg = shared.load_config()
    repo = cfg["repo"]
    limit = args.limit or cfg["limits"]["scroll_pool_size"]

    # Build the label filter: every WAYD post has the `wayd-post` label.
    # Adding a vibe filter narrows further.
    labels = ["wayd-post"]
    if args.vibe:
        if shared.vibe_by_slug(args.vibe) is None:
            shared.emit_error(f"Unknown vibe: {args.vibe}", code="bad_vibe")
            return
        labels.append(f"vibe:{args.vibe}")

    label_args = []
    for lb in labels:
        label_args += ["--label", lb]

    try:
        raw = shared.gh(
            [
                "issue", "list",
                "--repo", repo,
                "--state", "open",  # closed = soft-deleted
                "--limit", str(limit),
                *label_args,
                "--json", "number,title,body,author,createdAt,reactionGroups,comments",
            ],
            json_output=True,
        )
    except shared.GhError as e:
        shared.emit_error(shared.translate_gh_error(e), code="gh_failed")
        return

    blocked = shared.load_blocked()
    posts = []
    for raw_post in raw or []:
        author = raw_post.get("author", {}).get("login", "")
        if author in blocked:
            continue
        parsed = shared.parse_post_body(raw_post.get("body", ""))
        if parsed["deleted"] or parsed["vibe"] is None:
            continue
        vibe = shared.vibe_by_slug(parsed["vibe"])
        # NOTE: `gh issue list --json comments` caps the comments array at
        # 100 per issue. For posts with more, reply_count maxes out at 100.
        # The orchestrator should render "100+" when reply_count_capped is
        # true. Getting the true count would require a per-issue REST call,
        # which is too costly for a 200-post scroll pool.
        comments = raw_post.get("comments", []) or []
        reply_count = len(comments)
        posts.append({
            "id": raw_post["number"],
            "author": author,
            "vibe_slug": parsed["vibe"],
            "vibe_emoji": vibe["emoji"] if vibe else "",
            "text": parsed["text"],
            "created_at": raw_post["createdAt"],
            "created_relative": shared.relative_time(raw_post["createdAt"]),
            "reactions": shared.summarize_reactions(raw_post.get("reactionGroups", [])),
            "reply_count": reply_count,
            "reply_count_capped": reply_count >= 100,
        })

    shared.emit({"ok": True, "posts": posts, "count": len(posts)})


def cmd_thread(args: argparse.Namespace) -> None:
    if not shared.validate_post_id(args.post_id):
        shared.emit_error("Invalid post id.", code="bad_post_id")
        return

    cfg = shared.load_config()
    repo = cfg["repo"]

    try:
        raw = shared.gh(
            [
                "issue", "view", str(args.post_id),
                "--repo", repo,
                "--json", "number,title,body,author,createdAt,reactionGroups,comments",
            ],
            json_output=True,
        )
    except shared.GhError as e:
        shared.emit_error(shared.translate_gh_error(e), code="gh_failed")
        return

    parsed = shared.parse_post_body(raw.get("body", ""))
    if parsed["deleted"]:
        shared.emit_error("This post has been deleted by its author.", code="deleted")
        return

    vibe = shared.vibe_by_slug(parsed["vibe"]) if parsed["vibe"] else None
    blocked = shared.load_blocked()
    comments = []
    for c in raw.get("comments", []) or []:
        author = c.get("author", {}).get("login", "")
        if author in blocked:
            continue
        comments.append({
            "author": author,
            "text": c.get("body", "").strip(),
            "created_at": c.get("createdAt"),
            "created_relative": shared.relative_time(c["createdAt"]) if c.get("createdAt") else "",
        })

    post = {
        "id": raw["number"],
        "author": raw.get("author", {}).get("login", ""),
        "vibe_slug": parsed["vibe"],
        "vibe_emoji": vibe["emoji"] if vibe else "",
        "text": parsed["text"],
        "created_at": raw["createdAt"],
        "created_relative": shared.relative_time(raw["createdAt"]),
        "reactions": shared.summarize_reactions(raw.get("reactionGroups", [])),
    }
    shared.emit({"ok": True, "post": post, "comments": comments})


def main() -> None:
    parser = argparse.ArgumentParser(prog="scroll")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("--vibe", default=None)
    p_fetch.add_argument("--limit", type=int, default=None)
    p_fetch.set_defaults(func=cmd_fetch)

    p_thread = sub.add_parser("thread")
    p_thread.add_argument("--post-id", type=int, required=True)
    p_thread.set_defaults(func=cmd_thread)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
