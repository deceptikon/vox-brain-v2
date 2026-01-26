#!/usr/bin/env python3
import argparse
import json
import os
import sys

from core.engine import VoxEngine


def main():
    parser = argparse.ArgumentParser(
        description="VOX Brain v2 - Symbolic Code Intelligence"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index a project")
    index_parser.add_argument("path", help="Path to project root")
    index_parser.add_argument(
        "--project-id", help="Optional project id (e.g., 2ad33e6a...)", default=None
    )
    index_parser.add_argument(
        "--env",
        help="Path to .env file for DB credentials",
        default="/home/lexx/MyWork/tamga/backend/.env",
    )

    # Search command
    search_parser = subparsers.add_parser(
        "search", help="Search symbols in the database"
    )
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--project-id", help="Optional project id (e.g., 2ad33e6a...)", default=None
    )
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results")
    search_parser.add_argument(
        "--env",
        help="Path to .env file for DB credentials",
        default="/home/lexx/MyWork/tamga/backend/.env",
    )
    search_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default) or 'json' for structured JSON results",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        engine = VoxEngine(env_path=args.env)

        if args.command == "index":
            print(f"🏗️  Indexing project at {args.path} (id={args.project_id})...")
            engine.index_project(args.path, project_id=args.project_id)
            print("✅ Indexing complete.")

        elif args.command == "search":
            # Support json output for programmatic use
            if getattr(args, "format", "text") == "json":
                # compute embedding and fetch raw rows (structured)
                q_emb = engine.embeddings.get_embeddings([args.query])[0]
                rows = engine.storage.search_hybrid(
                    args.query, q_emb, limit=args.limit, project_id=args.project_id
                )
                results = []
                for r in rows:
                    # SELECT order: name, symbol_type, file_path, project_id, project_path, code, docstring, distance, name_priority
                    (
                        name,
                        stype,
                        path,
                        proj_id,
                        proj_path,
                        code,
                        docs,
                        dist,
                        priority,
                    ) = r
                    results.append(
                        {
                            "name": name,
                            "type": stype,
                            "file_path": path,
                            "project_id": proj_id,
                            "project_path": proj_path,
                            "code": code,
                            "docstring": docs,
                            "distance": float(dist) if dist is not None else None,
                            "priority": priority,
                        }
                    )
                print(json.dumps(results, ensure_ascii=False))
            else:
                context = engine.ask(args.query, project_id=args.project_id)
                print(context)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
