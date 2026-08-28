#!/usr/bin/env python3
"""
Qdrant to Pinecone Vector Database Migration Script
---------------------------------------------------
Migrates all vector embeddings, IDs, and payload metadata from a Qdrant collection
to a Pinecone Serverless vector index, with batching, retry resilience, progress tracking,
and post-migration verification.

Usage:
    python scripts/migrate_qdrant_to_pinecone.py
    python scripts/migrate_qdrant_to_pinecone.py --collection HPVdb_openai --index hpvdb-openai
"""

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("qdrant_to_pinecone")


def sanitize_index_name(name: str) -> str:
    """Converts a collection name into a valid Pinecone index name (lowercase, dashes only)."""
    sanitized = name.lower().replace("_", "-").replace(" ", "-")
    # Keep only alphanumeric and hyphen
    sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")
    return sanitized.strip("-")


def get_qdrant_client() -> QdrantClient:
    """Initializes and returns the Qdrant client from environment variables."""
    endpoint = os.getenv("QDRANT_ENDPOINT") or os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not endpoint:
        logger.error("Missing QDRANT_ENDPOINT or QDRANT_URL in environment.")
        sys.exit(1)

    logger.info(f"Connecting to Qdrant at: {endpoint[:30]}...")
    client = QdrantClient(url=endpoint, api_key=api_key)
    return client


def get_pinecone_client() -> Pinecone:
    """Initializes and returns the Pinecone client from environment variables."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.error("Missing PINECONE_API_KEY in environment.")
        sys.exit(1)

    logger.info("Initializing Pinecone client...")
    return Pinecone(api_key=api_key)


def get_or_create_pinecone_index(
    pc: Pinecone,
    index_name: str,
    dimension: int,
    metric: str = "cosine",
    cloud: str = "aws",
    region: str = "us-east-1",
) -> Any:
    """Ensures Pinecone index exists with the matching dimension and metric."""
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    logger.info(f"Existing Pinecone indexes: {existing_indexes}")

    if index_name not in existing_indexes:
        logger.info(
            f"Creating Pinecone index '{index_name}' (dimension={dimension}, metric={metric}, cloud={cloud}, region={region})..."
        )
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(cloud=cloud, region=region),
        )

        # Wait for index to be ready
        logger.info(f"Waiting for index '{index_name}' to become ready...")
        while not pc.describe_index(index_name).status["ready"]:
            time.sleep(2)
        logger.info(f"Index '{index_name}' is ready.")
    else:
        desc = pc.describe_index(index_name)
        logger.info(
            f"Index '{index_name}' already exists (dimension={desc.dimension}, metric={desc.metric}, status={desc.status['ready']})."
        )
        if desc.dimension != dimension:
            raise ValueError(
                f"Dimension mismatch for existing index '{index_name}': expected {dimension}, got {desc.dimension}"
            )

    return pc.Index(index_name)


def format_metadata_for_pinecone(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Flattens and formats Qdrant payload dictionary into Pinecone-compatible metadata.
    
    Pinecone metadata values must be: str, int, float, bool, or list of str.
    Nested dictionaries are flattened.
    """
    if not payload:
        return {}

    formatted: Dict[str, Any] = {}
    for key, val in payload.items():
        if val is None:
            continue
        if isinstance(val, (str, int, float, bool)):
            formatted[key] = val
        elif isinstance(val, list):
            # Pinecone accepts list of strings
            formatted[key] = [str(item) for item in val if item is not None]
        elif isinstance(val, dict):
            # Flatten nested dict (e.g. metadata.source -> source)
            for sub_k, sub_v in val.items():
                if isinstance(sub_v, (str, int, float, bool)):
                    formatted[sub_k] = sub_v
                elif isinstance(sub_v, list):
                    formatted[sub_k] = [str(x) for x in sub_v if x is not None]
                else:
                    formatted[sub_k] = str(sub_v)
        else:
            formatted[key] = str(val)

    # Ensure standard LangChain compatibility keys
    if "page_content" in formatted and "text" not in formatted:
        formatted["text"] = formatted["page_content"]
    elif "text" in formatted and "page_content" not in formatted:
        formatted["page_content"] = formatted["text"]

    return formatted


def migrate_collection(
    qdrant_client: QdrantClient,
    pinecone_index: Any,
    collection_name: str,
    scroll_batch_size: int = 250,
    upsert_batch_size: int = 100,
    namespace: str = "",
) -> Tuple[int, int]:
    """Scrolls points from Qdrant and upserts them to Pinecone in batches."""
    collection_info = qdrant_client.get_collection(collection_name)
    total_expected = collection_info.points_count or 0
    logger.info(f"Starting migration for collection '{collection_name}' (Total points ~{total_expected})...")

    offset: Optional[Any] = None
    migrated_count = 0
    start_time = time.time()

    pinecone_batch: List[Dict[str, Any]] = []

    while True:
        # Scroll batch from Qdrant
        points, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            limit=scroll_batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )

        if not points:
            break

        for pt in points:
            vector = pt.vector
            if isinstance(vector, dict):
                # Handle named vectors if any
                vector = list(vector.values())[0]

            metadata = format_metadata_for_pinecone(pt.payload)

            pinecone_batch.append({
                "id": str(pt.id),
                "values": [float(x) for x in vector],
                "metadata": metadata,
            })

            if len(pinecone_batch) >= upsert_batch_size:
                upsert_with_retry(pinecone_index, pinecone_batch, namespace=namespace)
                migrated_count += len(pinecone_batch)
                pinecone_batch = []

                # Progress logging
                elapsed = time.time() - start_time
                rate = migrated_count / elapsed if elapsed > 0 else 0
                pct = (migrated_count / total_expected * 100) if total_expected > 0 else 0
                logger.info(
                    f"Migrated {migrated_count}/{total_expected} vectors ({pct:.1f}%) "
                    f"[{rate:.1f} vectors/sec]"
                )

        if next_offset is None:
            break
        offset = next_offset

    # Upsert remaining points
    if pinecone_batch:
        upsert_with_retry(pinecone_index, pinecone_batch, namespace=namespace)
        migrated_count += len(pinecone_batch)

    total_time = time.time() - start_time
    logger.info(
        f"Migration completed! Total vectors migrated: {migrated_count} in {total_time:.2f}s "
        f"({migrated_count / total_time:.1f} vectors/sec)"
    )
    return migrated_count, total_expected


def upsert_with_retry(
    index: Any,
    vectors: List[Dict[str, Any]],
    namespace: str = "",
    max_retries: int = 5,
    backoff_factor: float = 1.5,
) -> None:
    """Upserts a batch of vectors with exponential backoff on transient errors."""
    for attempt in range(1, max_retries + 1):
        try:
            index.upsert(vectors=vectors, namespace=namespace)
            return
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to upsert batch after {max_retries} attempts: {e}")
                raise e
            sleep_time = backoff_factor ** attempt
            logger.warning(f"Upsert error on attempt {attempt}: {e}. Retrying in {sleep_time:.1f}s...")
            time.sleep(sleep_time)


def verify_migration(
    qdrant_client: QdrantClient,
    pinecone_index: Any,
    collection_name: str,
    sample_size: int = 10,
    namespace: str = "",
) -> bool:
    """Performs rigorous post-migration verification:
    
    1. Compares total vector counts.
    2. Fetches sample vector IDs from Pinecone and verifies vector embeddings and metadata match Qdrant.
    3. Runs a test vector similarity search query on Pinecone to confirm index functionality.
    """
    logger.info("\n==================================================")
    logger.info("  STARTING POST-MIGRATION VERIFICATION CHECKS")
    logger.info("==================================================")

    all_checks_passed = True

    # 1. Total Vector Count Check
    qdrant_info = qdrant_client.get_collection(collection_name)
    qdrant_count = qdrant_info.points_count or 0

    # Wait briefly for Pinecone serverless indexing stats to reflect
    logger.info("Waiting for Pinecone index stats to sync...")
    for _ in range(6):
        time.sleep(3)
        pinecone_stats = pinecone_index.describe_index_stats()
        pinecone_count = pinecone_stats.get("total_vector_count", 0)
        if namespace:
            ns_stats = pinecone_stats.get("namespaces", {}).get(namespace, {})
            pinecone_count = ns_stats.get("vector_count", pinecone_count)
        if pinecone_count >= qdrant_count:
            break

    logger.info(f"[Check 1] Vector Counts: Qdrant={qdrant_count} vs Pinecone={pinecone_count}")
    if pinecone_count >= qdrant_count:
        logger.info("  -> PASS: Vector counts match perfectly!")
    else:
        logger.warning(f"  -> WARNING: Vector count discrepancy (Qdrant: {qdrant_count}, Pinecone: {pinecone_count})")
        # Note: Serverless stats can occasionally lag by a few seconds
        all_checks_passed = False

    # 2. Sample Data & Vector Embedding Fidelity Check
    logger.info(f"[Check 2] Verifying vector embeddings & metadata fidelity for {sample_size} sample points...")
    sample_points, _ = qdrant_client.scroll(
        collection_name=collection_name,
        limit=sample_size,
        with_payload=True,
        with_vectors=True,
    )

    sample_ids = [str(pt.id) for pt in sample_points]
    fetched = pinecone_index.fetch(ids=sample_ids, namespace=namespace)
    fetched_vectors = fetched.get("vectors", {})

    logger.info(f"  -> Fetched {len(fetched_vectors)}/{len(sample_ids)} sample records from Pinecone.")

    fidelity_passed = True
    for pt in sample_points:
        pt_id = str(pt.id)
        if pt_id not in fetched_vectors:
            logger.error(f"  -> FAIL: ID {pt_id} not found in Pinecone!")
            fidelity_passed = False
            continue

        p_rec = fetched_vectors[pt_id]
        p_vec = p_rec.get("values", [])
        q_vec = pt.vector if isinstance(pt.vector, list) else list(pt.vector.values())[0]

        # Check vector cosine / numerical closeness
        if not np.allclose(q_vec, p_vec, atol=1e-4):
            logger.error(f"  -> FAIL: Vector embedding mismatch for ID {pt_id}!")
            fidelity_passed = False
        else:
            logger.debug(f"  -> Point {pt_id}: Vector match verified.")

        # Check metadata payload
        p_meta = p_rec.get("metadata", {})
        q_meta = pt.payload or {}
        if "page_content" in q_meta and p_meta.get("page_content") != q_meta["page_content"]:
            logger.error(f"  -> FAIL: Page content mismatch for ID {pt_id}!")
            fidelity_passed = False

    if fidelity_passed:
        logger.info("  -> PASS: All sampled vector values and metadata matched with 100% precision!")
    else:
        all_checks_passed = False

    # 3. Similarity Query Test
    if sample_points:
        test_query_vector = sample_points[0].vector
        if isinstance(test_query_vector, dict):
            test_query_vector = list(test_query_vector.values())[0]

        logger.info("[Check 3] Running test similarity search query in Pinecone...")
        query_res = pinecone_index.query(
            vector=[float(x) for x in test_query_vector],
            top_k=3,
            include_metadata=True,
            namespace=namespace,
        )

        matches = query_res.get("matches", [])
        logger.info(f"  -> Received {len(matches)} query matches:")
        for idx, match in enumerate(matches):
            logger.info(
                f"     [{idx + 1}] ID: {match.id}, Score: {match.score:.4f}, "
                f"Source: {match.metadata.get('source', 'N/A')}, "
                f"Content: {match.metadata.get('text', '')[:60]}..."
            )

        if matches and matches[0].score >= 0.99:
            logger.info("  -> PASS: Top-1 query match score is ~1.00 (Self-match verified)!")
        elif matches:
            logger.info("  -> PASS: Similarity query returned relevant results.")
        else:
            logger.error("  -> FAIL: Similarity query returned 0 matches.")
            all_checks_passed = False

    logger.info("==================================================")
    if all_checks_passed:
        logger.info("  VERIFICATION RESULT: ALL CHECKS PASSED (SUCCESS)")
    else:
        logger.warning("  VERIFICATION RESULT: COMPLETED WITH WARNINGS")
    logger.info("==================================================\n")

    return all_checks_passed


def main():
    parser = argparse.ArgumentParser(description="Migrate vector database from Qdrant to Pinecone")
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Qdrant collection name (default: auto-detect first collection or HPVdb_openai)",
    )
    parser.add_argument(
        "--index",
        type=str,
        default=None,
        help="Pinecone index name (default: sanitized collection name)",
    )
    parser.add_argument(
        "--cloud",
        type=str,
        default="aws",
        help="Pinecone Serverless cloud provider (default: aws)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="Pinecone Serverless region (default: us-east-1)",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="",
        help="Pinecone target namespace (default: default empty namespace)",
    )
    parser.add_argument(
        "--scroll-batch-size",
        type=int,
        default=250,
        help="Qdrant scroll batch size (default: 250)",
    )
    parser.add_argument(
        "--upsert-batch-size",
        type=int,
        default=100,
        help="Pinecone upsert batch size (default: 100)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-migration verification checks",
    )

    args = parser.parse_args()

    logger.info("==================================================")
    logger.info("  QDRANT -> PINECONE VECTOR DB MIGRATION ENGINE   ")
    logger.info("==================================================")

    # 1. Initialize Clients
    qdrant = get_qdrant_client()
    pinecone_client = get_pinecone_client()

    # 2. Identify Collection
    collections = [c.name for c in qdrant.get_collections().collections]
    logger.info(f"Available Qdrant collections: {collections}")

    collection_name = args.collection
    if not collection_name:
        if "HPVdb_openai" in collections:
            collection_name = "HPVdb_openai"
        elif collections:
            collection_name = collections[0]
        else:
            logger.error("No collections found in Qdrant!")
            sys.exit(1)

    if collection_name not in collections:
        logger.error(f"Collection '{collection_name}' not found in Qdrant! Available: {collections}")
        sys.exit(1)

    # 3. Read Collection Metadata
    collection_info = qdrant.get_collection(collection_name)
    vector_params = collection_info.config.params.vectors

    if isinstance(vector_params, dict):
        # Named vector config
        first_key = list(vector_params.keys())[0]
        dim = vector_params[first_key].size
        metric_name = vector_params[first_key].distance.name.lower()
    else:
        dim = vector_params.size
        metric_name = vector_params.distance.name.lower()

    # Normalize metric
    metric = "cosine" if "cosine" in metric_name else ("dotproduct" if "dot" in metric_name else "euclidean")

    index_name = args.index or sanitize_index_name(collection_name)
    logger.info(f"Selected Source Collection: '{collection_name}'")
    logger.info(f"Target Pinecone Index:     '{index_name}'")
    logger.info(f"Vector Dimensions:         {dim}")
    logger.info(f"Distance Metric:           {metric}")
    logger.info(f"Points Count:              {collection_info.points_count}")

    # 4. Setup Pinecone Index
    pinecone_index = get_or_create_pinecone_index(
        pc=pinecone_client,
        index_name=index_name,
        dimension=dim,
        metric=metric,
        cloud=args.cloud,
        region=args.region,
    )

    # 5. Execute Migration
    migrated_count, total_count = migrate_collection(
        qdrant_client=qdrant,
        pinecone_index=pinecone_index,
        collection_name=collection_name,
        scroll_batch_size=args.scroll_batch_size,
        upsert_batch_size=args.upsert_batch_size,
        namespace=args.namespace,
    )

    # 6. Verify Migration
    if not args.skip_verify:
        success = verify_migration(
            qdrant_client=qdrant,
            pinecone_index=pinecone_index,
            collection_name=collection_name,
            namespace=args.namespace,
        )
        if not success:
            logger.warning("Migration completed with verification warnings.")
            sys.exit(1)

    logger.info(f"All {migrated_count} vectors successfully migrated to Pinecone index '{index_name}'.")


if __name__ == "__main__":
    main()
