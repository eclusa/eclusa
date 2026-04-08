"""knowledge/community.py — Community detection via label propagation (KG-05).

Label propagation runs in pure Python over adjacency loaded from the fact table.
Only currently valid facts (t_invalid IS NULL) contribute to the graph.

On each run, communities are fully replaced (DELETE + INSERT in a single transaction)
to ensure the community table always reflects the current graph state.
"""

import logging
import random

import asyncpg

logger = logging.getLogger(__name__)


async def run_label_propagation(
    conn: asyncpg.Connection,
    max_iterations: int = 10,
) -> None:
    """Label propagation community detection.

    1. Load entity adjacency from fact table (currently valid facts only).
    2. Assign each entity its own label initially.
    3. Each iteration: each entity adopts the plurality label of its neighbors.
       Random shuffle order on each iteration reduces label oscillation.
    4. Terminate early when stable (no entity changed label in the iteration).
    5. Write resulting communities to community table (atomically replaces all).

    Single entities with no neighbors form their own single-member community
    and are included in the output.

    Args:
        conn: asyncpg database connection
        max_iterations: maximum number of propagation iterations (default: 10)
    """
    # Step 1: load adjacency from currently valid facts
    rows = await conn.fetch(
        "SELECT source_entity::text, target_entity::text FROM fact WHERE t_invalid IS NULL"
    )

    if not rows:
        # No facts -> no communities to write; graceful empty case
        async with conn.transaction():
            await conn.execute("DELETE FROM community")
        logger.debug("run_label_propagation: no facts found, community table cleared")
        return

    # Build undirected adjacency dict
    adjacency: dict[str, set[str]] = {}
    for row in rows:
        src = row["source_entity"]
        tgt = row["target_entity"]
        adjacency.setdefault(src, set()).add(tgt)
        adjacency.setdefault(tgt, set()).add(src)

    # Step 2: each entity starts with its own label
    labels: dict[str, str] = {entity: entity for entity in adjacency}

    # Step 3: iteratively adopt plurality neighbor label
    for iteration in range(max_iterations):
        stable = True
        entities = list(adjacency.keys())
        random.shuffle(entities)  # random update order reduces oscillation

        for entity in entities:
            neighbors = adjacency.get(entity, set())
            if not neighbors:
                continue  # isolated entities keep their own label

            # Count neighbor labels
            label_counts: dict[str, int] = {}
            for neighbor in neighbors:
                label = labels.get(neighbor, neighbor)
                label_counts[label] = label_counts.get(label, 0) + 1

            # Adopt plurality label (ties broken by max() -> lexicographic)
            new_label = max(label_counts, key=label_counts.__getitem__)
            if new_label != labels[entity]:
                labels[entity] = new_label
                stable = False

        if stable:
            logger.debug(
                "run_label_propagation: stable after %d iterations", iteration + 1
            )
            break

    # Step 4: group entities by label to form communities
    communities: dict[str, list[str]] = {}
    for entity, label in labels.items():
        communities.setdefault(label, []).append(entity)

    # Step 5: atomic replace — DELETE all then INSERT all communities
    async with conn.transaction():
        await conn.execute("DELETE FROM community")
        for label_id, members in communities.items():
            await conn.execute(
                """
                INSERT INTO community (id, name, entity_ids, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2::uuid[], NOW(), NOW())
                """,
                f"community_{label_id[:8]}",
                members,
            )

    logger.debug(
        "run_label_propagation: wrote %d communities for %d entities",
        len(communities),
        len(labels),
    )
