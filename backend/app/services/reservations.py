from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import text

from app.core.database_pool import db_pool

# Aggregating from properties with a LEFT JOIN checks ownership in the same
# round trip: a property belonging to another tenant produces no row at all,
# while one that simply has no bookings yet produces a zeroed row.
TOTAL_REVENUE_QUERY = text("""
    SELECT
        p.id AS property_id,
        COALESCE(SUM(r.total_amount), 0) AS total_revenue,
        COUNT(r.id) AS reservation_count
    FROM properties p
    LEFT JOIN reservations r
        ON r.property_id = p.id AND r.tenant_id = p.tenant_id
    WHERE p.id = :property_id AND p.tenant_id = :tenant_id
    GROUP BY p.id
""")

# Month boundaries are compared against the check-in time converted to the
# property's own timezone, so a booking lands in the month the client sees on
# their calendar rather than the month it happens to fall in under UTC.
MONTHLY_REVENUE_QUERY = text("""
    SELECT
        p.id AS property_id,
        COALESCE(SUM(r.total_amount), 0) AS total_revenue,
        COUNT(r.id) AS reservation_count
    FROM properties p
    LEFT JOIN reservations r
        ON r.property_id = p.id AND r.tenant_id = p.tenant_id
        AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_local
        AND (r.check_in_date AT TIME ZONE p.timezone) < :end_local
    WHERE p.id = :property_id AND p.tenant_id = :tenant_id
    GROUP BY p.id
""")

PROPERTIES_QUERY = text("""
    SELECT id, name, timezone
    FROM properties
    WHERE tenant_id = :tenant_id
    ORDER BY name
""")


async def _ensure_pool() -> None:
    """Initialises the shared connection pool on first use."""
    if db_pool.session_factory is None:
        await db_pool.initialize()


async def calculate_monthly_revenue(
    property_id: str, tenant_id: str, month: int, year: int
) -> Optional[Dict[str, Any]]:
    """
    Calculates revenue for a specific month, in the property's local timezone.
    Returns None when the property does not belong to the tenant.
    """

    # Naive datetimes on purpose: AT TIME ZONE yields a local timestamp, so the
    # bounds have to be local wall clock times rather than absolute instants.
    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)

    await _ensure_pool()

    async with db_pool.get_session() as session:
        result = await session.execute(MONTHLY_REVENUE_QUERY, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_local": start_date,
            "end_local": end_date
        })
        row = result.fetchone()

    if row is None:
        return None

    return {
        "property_id": row.property_id,
        "tenant_id": tenant_id,
        "total": str(row.total_revenue),
        "currency": "USD",
        "count": row.reservation_count,
        "period": f"{year:04d}-{month:02d}"
    }

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Aggregates revenue from database.
    Returns None when the property does not belong to the tenant.
    """
    await _ensure_pool()

    async with db_pool.get_session() as session:
        result = await session.execute(TOTAL_REVENUE_QUERY, {
            "property_id": property_id,
            "tenant_id": tenant_id
        })
        row = result.fetchone()

    if row is None:
        return None

    return {
        "property_id": row.property_id,
        "tenant_id": tenant_id,
        "total": str(row.total_revenue),
        "currency": "USD",
        "count": row.reservation_count,
        "period": None
    }


async def list_properties(tenant_id: str) -> List[Dict[str, Any]]:
    """
    Returns the properties belonging to a single tenant.
    """
    await _ensure_pool()

    async with db_pool.get_session() as session:
        result = await session.execute(PROPERTIES_QUERY, {"tenant_id": tenant_id})
        rows = result.fetchall()

    return [
        {"id": row.id, "name": row.name, "timezone": row.timezone}
        for row in rows
    ]
