"""Main loop: fetch each source, diff against state, push new items via Telegram."""
import argparse
from datetime import datetime, timezone

from fetch import load_state, save_state
from notify import notify
from sources import PARSERS, SOURCES


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_source(src: dict, state: dict, simulate_init: bool) -> None:
    name = src["name"]
    src_state = state.setdefault(name, {"initialized": False, "seen_ids": []})

    print(f"[{name}] ", end="", flush=True)
    parser_fn = PARSERS[src["parser"]]
    try:
        items = parser_fn(src)
    except Exception as e:
        print(f"FETCH/PARSE ERROR: {e}")
        return

    # Optional case-insensitive title substring filter (per-source config).
    keyword = src.get("title_includes")
    if keyword:
        kw = keyword.lower()
        before = len(items)
        items = [it for it in items if kw in it["title"].lower()]
        if before != len(items):
            print(f"[filter '{keyword}': {before}->{len(items)}] ", end="", flush=True)
    if not items:
        print("no items returned, skipping.")
        return

    if not src_state["initialized"]:
        if simulate_init:
            seed = items[1:]
            skipped = items[0]
            print(
                f"[simulate-init] seeded {len(seed)}, "
                f"skipped newest: {skipped['title'][:50]!r}"
            )
        else:
            seed = items
            print(f"[init] seeded {len(seed)} items, no notification.")
        src_state["seen_ids"] = [it["id"] for it in seed]
        src_state["initialized"] = True
        src_state["last_run"] = now_iso()
        return

    seen = set(src_state["seen_ids"])
    new_items = [it for it in items if it["id"] not in seen]

    if not new_items:
        src_state["last_run"] = now_iso()
        print("no new.")
        return

    print(f"{len(new_items)} new -> notify...", flush=True)
    # Oldest-first so the newest sits at the bottom of the chat.
    for it in reversed(new_items):
        if notify(name, it["title"], it["url"]):
            src_state["seen_ids"].append(it["id"])
            print(f"    ✓ {it['title'][:60]}")
        else:
            print(f"    ✗ FAILED, will retry next run: {it['title'][:60]}")
    src_state["last_run"] = now_iso()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate-init", action="store_true",
                    help="For uninitialized sources, skip newest 1 item (so next run pushes it).")
    ap.add_argument("--source", action="append", default=None,
                    help="Only process the named source(s). Can be repeated.")
    args = ap.parse_args()

    if args.simulate_init:
        print("=== SIMULATE-INIT MODE: each uninitialized source skips its newest 1 item ===\n")

    sources = SOURCES
    if args.source:
        wanted = set(args.source)
        sources = [s for s in SOURCES if s["name"] in wanted]
        missing = wanted - {s["name"] for s in sources}
        if missing:
            print(f"⚠ unknown source(s): {sorted(missing)}")
        if not sources:
            print("no matching sources, exiting.")
            return
        print(f"filtering to: {[s['name'] for s in sources]}\n")

    state = load_state()
    for src in sources:
        process_source(src, state, simulate_init=args.simulate_init)
        save_state(state)
    print("\nDone.")


if __name__ == "__main__":
    main()
