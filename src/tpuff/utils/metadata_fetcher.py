"""Namespace metadata fetching utilities."""

import concurrent.futures
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tpuff.client import clear_client_cache, get_namespace, get_turbopuffer_client
from tpuff.utils.debug import debug_log
from tpuff.utils.regions import TURBOPUFFER_REGIONS


@dataclass
class RecallData:
    """Recall metrics for a namespace."""

    avg_recall: float
    avg_ann_count: float
    avg_exhaustive_count: float


@dataclass
class NamespaceMetadata:
    """Metadata for a namespace."""

    approx_row_count: int
    approx_logical_bytes: int
    index: dict[str, Any]
    updated_at: str | datetime
    created_at: str | datetime
    schema: dict[str, Any]
    encryption: dict[str, Any] | None = None


@dataclass
class NamespaceWithMetadata:
    """A namespace with its metadata."""

    namespace_id: str
    metadata: NamespaceMetadata | None
    region: str | None = None
    recall: RecallData | None = None


def fetch_recall_data(namespace_id: str, region: str | None = None) -> RecallData | None:
    """Fetch recall metrics for a namespace.

    Args:
        namespace_id: The namespace ID.
        region: Optional region override.

    Returns:
        RecallData or None if fetch fails.
    """
    try:
        debug_log(f"Fetching recall for namespace: {namespace_id}", {})
        ns = get_namespace(namespace_id, region)
        recall_response = ns.recall(num=25, top_k=10)
        debug_log(f"Recall for {namespace_id}", recall_response)
        return RecallData(
            avg_recall=recall_response.avg_recall,
            avg_ann_count=recall_response.avg_ann_count,
            avg_exhaustive_count=recall_response.avg_exhaustive_count,
        )
    except Exception as e:
        debug_log(f"Failed to fetch recall for {namespace_id}", str(e))
        return None


def fetch_namespace_metadata(namespace_id: str, region: str | None = None) -> NamespaceMetadata | None:
    """Fetch metadata for a single namespace.

    Args:
        namespace_id: The namespace ID.
        region: Optional region override.

    Returns:
        NamespaceMetadata or None if fetch fails.
    """
    try:
        debug_log(f"Fetching metadata for namespace: {namespace_id}", {})
        ns = get_namespace(namespace_id, region)
        metadata = ns.metadata()
        debug_log(f"Metadata for {namespace_id}", metadata)

        # Handle the metadata response - it might have different attributes
        index_data = {"status": "up-to-date"}
        if hasattr(metadata, "index") and metadata.index:
            if hasattr(metadata.index, "status"):
                index_data = {"status": metadata.index.status}
                if hasattr(metadata.index, "unindexed_bytes"):
                    index_data["unindexed_bytes"] = metadata.index.unindexed_bytes
            elif isinstance(metadata.index, dict):
                index_data = metadata.index

        schema_data = {}
        if hasattr(metadata, "schema") and metadata.schema:
            if isinstance(metadata.schema, dict):
                schema_data = metadata.schema
            else:
                # Convert schema object to dict
                schema_data = dict(metadata.schema) if hasattr(metadata.schema, "__iter__") else {}

        encryption_data = None
        if hasattr(metadata, "encryption") and metadata.encryption:
            encryption_data = metadata.encryption if isinstance(metadata.encryption, dict) else None

        return NamespaceMetadata(
            approx_row_count=metadata.approx_row_count,
            approx_logical_bytes=metadata.approx_logical_bytes,
            index=index_data,
            updated_at=metadata.updated_at,
            created_at=metadata.created_at,
            schema=schema_data,
            encryption=encryption_data,
        )
    except Exception as e:
        debug_log(f"Failed to fetch metadata for {namespace_id}", str(e))
        return None


def fetch_namespaces_with_metadata(
    all_regions: bool = False,
    region: str | None = None,
    include_recall: bool = False,
) -> list[NamespaceWithMetadata]:
    """Fetch namespaces with their metadata from Turbopuffer API.

    Supports both single-region and multi-region queries.

    Args:
        all_regions: If True, query all regions.
        region: Specific region to query (ignored if all_regions is True).
        include_recall: If True, include recall metrics.

    Returns:
        List of NamespaceWithMetadata objects.
    """
    namespaces_with_metadata: list[NamespaceWithMetadata] = []

    if all_regions:
        # Query all regions
        debug_log("Querying all regions", {"regionCount": len(TURBOPUFFER_REGIONS)})

        for current_region in TURBOPUFFER_REGIONS:
            try:
                # Clear cache to ensure we get a new client for the new region
                clear_client_cache()
                client = get_turbopuffer_client(current_region)
                namespaces_response = client.namespaces()
                debug_log(f"Namespaces in {current_region}", namespaces_response)

                namespaces = list(namespaces_response)
                if namespaces:
                    # Fetch metadata for namespaces in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        metadata_futures = {
                            executor.submit(fetch_namespace_metadata, ns.id, current_region): ns
                            for ns in namespaces
                        }
                        metadata_map = {}
                        for future in concurrent.futures.as_completed(metadata_futures):
                            ns = metadata_futures[future]
                            metadata_map[ns.id] = future.result()

                    # Fetch recall data in parallel if requested
                    recall_map: dict[str, RecallData | None] = {}
                    if include_recall:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                            recall_futures = {
                                executor.submit(fetch_recall_data, ns.id, current_region): ns
                                for ns in namespaces
                            }
                            for future in concurrent.futures.as_completed(recall_futures):
                                ns = recall_futures[future]
                                recall_map[ns.id] = future.result()
                    else:
                        for ns in namespaces:
                            recall_map[ns.id] = None

                    # Add namespaces from this region with region info
                    for ns in namespaces:
                        namespaces_with_metadata.append(
                            NamespaceWithMetadata(
                                namespace_id=ns.id,
                                metadata=metadata_map.get(ns.id),
                                region=current_region,
                                recall=recall_map.get(ns.id),
                            )
                        )
            except Exception as e:
                debug_log(f"Failed to query region {current_region}", str(e))
                # Continue to next region on error
                continue
    else:
        # Query single region
        client = get_turbopuffer_client(region)
        namespaces_response = client.namespaces()
        debug_log("Namespaces API Response", namespaces_response)
        namespaces = list(namespaces_response)

        if not namespaces:
            return []

        # Fetch metadata for each namespace in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            metadata_futures = {
                executor.submit(fetch_namespace_metadata, ns.id, region): ns for ns in namespaces
            }
            metadata_map = {}
            for future in concurrent.futures.as_completed(metadata_futures):
                ns = metadata_futures[future]
                metadata_map[ns.id] = future.result()

        # Fetch recall data in parallel if requested
        recall_map: dict[str, RecallData | None] = {}
        if include_recall:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                recall_futures = {
                    executor.submit(fetch_recall_data, ns.id, region): ns for ns in namespaces
                }
                for future in concurrent.futures.as_completed(recall_futures):
                    ns = recall_futures[future]
                    recall_map[ns.id] = future.result()
        else:
            for ns in namespaces:
                recall_map[ns.id] = None

        # Combine namespaces with their metadata
        for ns in namespaces:
            namespaces_with_metadata.append(
                NamespaceWithMetadata(
                    namespace_id=ns.id,
                    metadata=metadata_map.get(ns.id),
                    region=region,
                    recall=recall_map.get(ns.id),
                )
            )

    return namespaces_with_metadata


def get_encryption_type(metadata: NamespaceMetadata | None) -> str:
    """Extract encryption type from metadata.

    Args:
        metadata: The namespace metadata.

    Returns:
        'cmek' or 'sse'.
    """
    if not metadata or not metadata.encryption:
        return "sse"  # Default to SSE

    if metadata.encryption.get("cmek"):
        return "cmek"

    return "sse"


def get_index_status(metadata: NamespaceMetadata | None) -> str:
    """Extract index status from metadata.

    Args:
        metadata: The namespace metadata.

    Returns:
        'up-to-date' or 'updating'.
    """
    if not metadata or not metadata.index:
        return "up-to-date"

    return metadata.index.get("status", "up-to-date")


def get_unindexed_bytes(metadata: NamespaceMetadata | None) -> int:
    """Get unindexed bytes from metadata.

    Args:
        metadata: The namespace metadata.

    Returns:
        Number of unindexed bytes.
    """
    if not metadata or not metadata.index:
        return 0

    if metadata.index.get("status") == "up-to-date":
        return 0

    return metadata.index.get("unindexed_bytes", 0)
