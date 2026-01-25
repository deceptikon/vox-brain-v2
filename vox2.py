#!/usr/bin/env python3
import argparse
import sys
import os
from core.engine import VoxEngine

def main():
    parser = argparse.ArgumentParser(description="VOX Brain v2 - Symbolic Code Intelligence")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index a project")
    index_parser.add_argument("path", help="Path to project root")
    index_parser.add_argument("--env", help="Path to .env file for DB credentials", default="/home/lexx/MyWork/tamga/backend/.env")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search symbols in the database")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results")
    search_parser.add_argument("--env", help="Path to .env file for DB credentials", default="/home/lexx/MyWork/tamga/backend/.env")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        engine = VoxEngine(env_path=args.env)
        
        if args.command == "index":
            print(f"🏗️  Indexing project at {args.path}...")
            engine.index_project(args.path)
            print("✅ Indexing complete.")
            
        elif args.command == "search":
            context = engine.ask(args.query)
            print(context)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
