"""Hesitation clustering and aggregation for pause penalties."""
from __future__ import annotations

from typing import Any, Dict, List

from .rules import HESITATION_CLUSTER_WINDOW, MAX_PUNCTUATION_PENALTY


def apply_hesitation_clustering(
    pause_results: List[Dict[str, Any]],
    window: float = HESITATION_CLUSTER_WINDOW
) -> List[Dict[str, Any]]:
    """Apply hesitation clustering to amplify penalties for consecutive pauses.
    
    PTE penalizes multiple small pauses close together more than isolated ones.
    This function identifies clusters of pauses within the time window and amplifies
    their penalties.
    
    Args:
        pause_results: List of pause evaluation results with 'penalty', 'start', 'end' fields
        window: Time window in seconds for clustering (default: 2.0)
        
    Returns:
        List of pause results with amplified penalties for clustered pauses
    """
    if not pause_results:
        return pause_results
    
    # Create a copy to avoid modifying original
    results = [r.copy() for r in pause_results]
    
    # Sort by start time to process chronologically
    sorted_results = sorted(results, key=lambda x: x.get("start", 0) or 0)
    
    # Identify clusters: group pauses that are within window of each other
    clusters = []
    current_cluster = [0]  # Start with first pause
    
    for i in range(1, len(sorted_results)):
        prev_pause_end = sorted_results[i - 1].get("end") or sorted_results[i - 1].get("start", 0) or 0
        curr_pause_start = sorted_results[i].get("start", 0) or 0
        time_gap = curr_pause_start - prev_pause_end
        
        if time_gap <= window and time_gap >= 0:
            # Add to current cluster
            current_cluster.append(i)
        else:
            # Start new cluster
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
            current_cluster = [i]
    
    # Add last cluster if it has multiple pauses
    if len(current_cluster) > 1:
        clusters.append(current_cluster)
    
    # Amplify penalties for all pauses in clusters
    for cluster in clusters:
        cluster_size = len(cluster)
        # Each additional pause in cluster adds 20% penalty amplification
        amplification = 1.0 + 0.2 * (cluster_size - 1)
        for idx in cluster:
            sorted_results[idx]["penalty"] = min(
                sorted_results[idx].get("penalty", 0.0) * amplification, 1.0
            )
            sorted_results[idx]["cluster_size"] = cluster_size
    
    return results


def aggregate_pause_penalty(
    pause_results: List[Dict[str, Any]],
    max_penalty: float = MAX_PUNCTUATION_PENALTY
) -> float:
    """Aggregate pause penalties into a single fluency score component.
    
    Calculates mean penalty across all pauses, normalized by count, and caps
    the total contribution to fluency score.
    
    Args:
        pause_results: List of pause evaluation results with 'penalty' field
        max_penalty: Maximum total punctuation penalty contribution (default: 0.3)
        
    Returns:
        Aggregated penalty score (0.0-1.0), capped at max_penalty
    """
    if not pause_results:
        return 0.0
    
    # Extract penalties
    penalties = [p.get("penalty", 0.0) for p in pause_results]
    
    # Calculate mean penalty (normalized by count)
    mean_penalty = sum(penalties) / len(penalties)
    
    # Cap at maximum contribution
    final_penalty = min(mean_penalty, max_penalty)
    
    return final_penalty
