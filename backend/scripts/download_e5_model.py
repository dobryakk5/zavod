#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and save local E5 embedding model.")
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-small",
        help="HuggingFace model id",
    )
    parser.add_argument(
        "--output",
        default="models/multilingual-e5-small",
        help="Output directory",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = SentenceTransformer(args.model)
    model.save(str(output_path))
    print(f"Saved E5 model to: {output_path}")


if __name__ == "__main__":
    main()

