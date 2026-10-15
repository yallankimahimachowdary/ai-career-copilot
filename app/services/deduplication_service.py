"""
app/services/deduplication_service.py
------------------------------------
Job Posting Cross-Site and Cross-Location Deduplication Service (Phase B Round 3/4).

Merges cross-site and cross-location duplicates based on:
1. Normalized title & fuzzy title equivalence
2. Normalized company with prefix/suffix stripping (e.g. LMMF'S, Hospital) and spelling variation tolerance
3. Location similarity / matching
4. Description token Jaccard similarity (>= 0.35)

Preserves one canonical posting with all sources and locations tracked.
"""

from collections import defaultdict
import difflib
import re
from typing import Any, Dict, List, Tuple


def _normalize_str(s: Any) -> str:
    """Strip punctuation and whitespace, lowercase."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _clean_company_name(s: Any) -> str:
    """Normalize company name by stripping prefixes (e.g. LMMF'S), suffixes (Hospital, Pvt, Ltd), and punctuation."""
    val = re.sub(r"['\"]", "", str(s or "").lower())
    val = re.sub(r"^(?:lmmfs|lmmf|the|dr|m/s|ms)\b[\s,.]*", "", val)
    val = re.sub(r"\b(?:hospital|hospitals|clinic|center|centre|institute|pvt|ltd|private|limited|inc|llc|corp)\b", "", val)
    return re.sub(r"[^a-z0-9]", "", val)


def _companies_match(c1: str, c2: str) -> bool:
    """Check whether two company names match exactly or with prefix/suffix/spelling variations."""
    if not c1 or not c2:
        return False
    norm1 = _normalize_str(c1)
    norm2 = _normalize_str(c2)
    if norm1 == norm2:
        return True

    clean1 = _clean_company_name(c1)
    clean2 = _clean_company_name(c2)
    if not clean1 or not clean2:
        return False
    if clean1 == clean2:
        return True

    # Sequence similarity for spelling variations (e.g. mageshkar vs mangeshkar)
    ratio = difflib.SequenceMatcher(None, clean1, clean2).ratio()
    if ratio >= 0.80:
        return True

    # Substring match if sufficiently distinctive (>= 5 chars)
    if len(clean1) >= 5 and clean1 in clean2:
        return True
    if len(clean2) >= 5 and clean2 in clean1:
        return True

    return False


def _description_token_jaccard(desc1: str, desc2: str) -> float:
    """Compute token Jaccard similarity over word tokens."""
    w1 = set(re.findall(r"\b[a-z0-9]+\b", str(desc1 or "").lower()))
    w2 = set(re.findall(r"\b[a-z0-9]+\b", str(desc2 or "").lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


class DeduplicationService:
    """Service to detect and merge duplicate job postings."""

    def deduplicate_records(
        self,
        records: List[Dict[str, Any]],
        sim_threshold: float = 0.35,
    ) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
        """
        Deduplicates a list of job posting records.
        Returns:
            (canonical_records, num_merged, duplicate_clusters)
        """
        # 1. Group records primarily by normalized title
        by_title = defaultdict(list)
        for r in records:
            t = _normalize_str(r.get("title"))
            by_title[t].append(r)

        canonical_records: List[Dict[str, Any]] = []
        duplicate_clusters: List[Dict[str, Any]] = []
        merged_count = 0

        for t, group in by_title.items():
            if len(group) == 1:
                canonical_records.append(group[0])
                continue

            n = len(group)
            visited = [False] * n

            for i in range(n):
                if visited[i]:
                    continue
                cluster = [group[i]]
                visited[i] = True

                for j in range(i + 1, n):
                    if visited[j]:
                        continue

                    co_i = group[i].get("company") or group[i].get("company_name") or ""
                    co_j = group[j].get("company") or group[j].get("company_name") or ""

                    if not _companies_match(co_i, co_j):
                        continue

                    sim = _description_token_jaccard(
                        group[i].get("description", ""),
                        group[j].get("description", ""),
                    )
                    loc_i = _normalize_str(group[i].get("location"))
                    loc_j = _normalize_str(group[j].get("location"))

                    # Merge if same location with decent similarity or high description similarity across locations
                    if (loc_i == loc_j and sim >= 0.20) or sim >= sim_threshold:
                        cluster.append(group[j])
                        visited[j] = True

                if len(cluster) > 1:
                    merged_count += (len(cluster) - 1)
                    # Pick primary record: prefer one with longest description or richer metadata
                    primary = max(cluster, key=lambda x: len(str(x.get("description") or "")))
                    merged_rec = dict(primary)

                    sources = list(dict.fromkeys(filter(None, [x.get("source") for x in cluster])))
                    locations = list(dict.fromkeys(filter(None, [x.get("location") for x in cluster])))
                    source_urls = list(dict.fromkeys(filter(None, [x.get("source_url") or x.get("external_id") for x in cluster])))
                    duplicate_ids = [str(x.get("id") or x.get("external_id")) for x in cluster if x != primary]

                    merged_rec["duplicate_count"] = len(cluster)
                    merged_rec["merged_sources"] = sources
                    merged_rec["all_locations"] = locations
                    merged_rec["all_source_urls"] = source_urls
                    merged_rec["merged_duplicate_ids"] = duplicate_ids

                    canonical_records.append(merged_rec)
                    duplicate_clusters.append({
                        "canonical_id": str(primary.get("id") or primary.get("external_id")),
                        "title": primary.get("title"),
                        "company": primary.get("company") or primary.get("company_name"),
                        "merged_count": len(cluster),
                        "sources": sources,
                        "locations": locations,
                        "duplicate_ids": duplicate_ids,
                    })
                else:
                    canonical_records.append(cluster[0])

        return canonical_records, merged_count, duplicate_clusters

    def deduplicate_job_match_items(self, match_items: List[Any], limit: int = 10) -> List[Any]:
        """
        Deduplicate a list of JobMatchItem objects (ordered by match score) in-flight.
        When duplicates are detected, merges source info into the higher-ranking match
        and yields unique postings.
        """
        deduped: List[Any] = []
        for item in match_items:
            is_dup = False
            item_title_norm = _normalize_str(getattr(item, "title", ""))
            item_co = getattr(item, "company_name", "") or ""

            for existing in deduped:
                exist_title_norm = _normalize_str(getattr(existing, "title", ""))
                exist_co = getattr(existing, "company_name", "") or ""

                if item_title_norm == exist_title_norm and _companies_match(item_co, exist_co):
                    # Duplicate found: merge source info and increment duplicate count
                    existing.duplicate_count = getattr(existing, "duplicate_count", 1) + 1
                    # Track merged sources
                    merged = list(getattr(existing, "merged_sources", []) or [])
                    item_sources = getattr(item, "merged_sources", []) or []
                    item_src = getattr(item, "source", None)
                    candidates_to_add = list(item_sources)
                    if item_src:
                        candidates_to_add.append(item_src)
                    for src in candidates_to_add:
                        if src and src not in merged:
                            merged.append(src)
                    existing.merged_sources = merged
                    is_dup = True
                    break

            if not is_dup:
                deduped.append(item)
                if len(deduped) >= limit:
                    break

        return deduped


deduplication_service = DeduplicationService()
