"""Seed helper CLI."""
import argparse
from pathlib import Path
from app.core import DB, seed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--dealers", type=int, default=50)
    p.add_argument("--skus", type=int, default=200)
    a = p.parse_args()
    if a.db.exists():
        a.db.unlink()
    print(seed(a.db, dealers=a.dealers, skus=a.skus))


if __name__ == "__main__":
    main()
