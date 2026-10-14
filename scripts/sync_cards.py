import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.cards import sync_catalog

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", default="latest")
    args = parser.parse_args()
    print(json.dumps(sync_catalog(args.build), ensure_ascii=False, indent=2))
