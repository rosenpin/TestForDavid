#!/usr/bin/env python3
"""
Script to update existing photo metadata with CLIP embeddings.
This can be run directly to add CLIP embeddings to photos that were
processed before the CLIP feature was added.
"""

import asyncio
import argparse
from processors.update_clip_embeddings import update_photos_with_clip_embeddings

async def main():
    parser = argparse.ArgumentParser(description="Update existing photo metadata with CLIP embeddings")
    parser.add_argument("--data-dir", default="data", help="Directory containing photos and metadata")
    args = parser.parse_args()
    
    print(f"Starting CLIP embeddings update for photos in {args.data_dir}...")
    
    stats = await update_photos_with_clip_embeddings(args.data_dir)
    
    print("\nCLIP Embeddings Update Complete:")
    print(f"Total files: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Skipped (already had embeddings): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

if __name__ == "__main__":
    asyncio.run(main()) 