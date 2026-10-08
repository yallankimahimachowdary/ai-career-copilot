"""Neo4j graph database driver and connection lifecycle management."""

import asyncio
from typing import Any, Dict, List, Optional
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from app.core.config import settings
from app.core.logging import logger

_neo4j_driver: Optional[AsyncDriver] = None


def get_neo4j_driver() -> AsyncDriver:
    """Get or initialize the global Neo4j AsyncDriver singleton."""
    global _neo4j_driver
    if _neo4j_driver is None:
        logger.info(f"Initializing Neo4j driver connection to {settings.NEO4J_URI}...")
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=30 * 60,
            max_connection_pool_size=50,
            connection_acquisition_timeout=10.0,
        )
    return _neo4j_driver


async def close_neo4j_driver() -> None:
    """Close the global Neo4j AsyncDriver on application shutdown."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        logger.info("Closing Neo4j driver connection...")
        await _neo4j_driver.close()
        _neo4j_driver = None


async def check_neo4j_health() -> bool:
    """Verify Neo4j connectivity and return boolean status."""
    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS ping")
            record = await result.single()
            return bool(record and record["ping"] == 1)
    except Exception as exc:
        logger.warning(f"Neo4j health check failed: {exc}")
        return False


async def init_neo4j_schema() -> None:
    """Ensure uniqueness constraints and indexes exist in Neo4j."""
    constraints = [
        "CREATE CONSTRAINT candidate_id_unique IF NOT EXISTS FOR (c:Candidate) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT skill_name_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT job_id_unique IF NOT EXISTS FOR (j:JobPosting) REQUIRE j.id IS UNIQUE",
        "CREATE CONSTRAINT company_name_unique IF NOT EXISTS FOR (comp:Company) REQUIRE comp.name IS UNIQUE",
    ]
    indexes = [
        "CREATE INDEX skill_name_index IF NOT EXISTS FOR (s:Skill) ON (s.name)",
        "CREATE INDEX job_title_index IF NOT EXISTS FOR (j:JobPosting) ON (j.title)",
    ]

    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            for statement in constraints:
                try:
                    res = await session.run(statement)
                    await res.consume()
                except Exception as exc:
                    logger.debug(f"Constraint creation notice: {exc}")

            for statement in indexes:
                try:
                    res = await session.run(statement)
                    await res.consume()
                except Exception as exc:
                    logger.debug(f"Index creation notice: {exc}")

        logger.info("Neo4j graph schema constraints and indexes verified.")
    except Exception as exc:
        logger.warning(f"Failed to initialize Neo4j schema: {exc}")


async def execute_cypher(
    query: str,
    params: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False,
) -> List[Dict[str, Any]]:
    """Execute a Cypher query asynchronously and return list of result dictionaries."""
    params = params or {}
    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()
            return records
    except (ServiceUnavailable, SessionExpired) as conn_err:
        logger.warning(f"Neo4j connection error executing Cypher: {conn_err}")
        if raise_on_error:
            raise
        return []
    except Exception as exc:
        logger.error(f"Error executing Cypher query: {exc}", exc_info=True)
        if raise_on_error:
            raise
        return []
