import json
import redis.asyncio as redis
from typing import Dict, Any, Optional
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    period = f"{year:04d}-{month:02d}" if month and year else "all"

    # Property IDs are only unique within a tenant, so the tenant has to be part
    # of the key. Without it two clients sharing a property ID read each other's
    # revenue out of the cache.
    cache_key = f"revenue:{tenant_id}:{property_id}:{period}"

    # Try to get from cache
    cached = await redis_client.get(cache_key)
    if cached:
        result = json.loads(cached)
        if result.get("tenant_id") == tenant_id:
            return result

    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_monthly_revenue, calculate_total_revenue

    # Calculate revenue
    if period == "all":
        result = await calculate_total_revenue(property_id, tenant_id)
    else:
        result = await calculate_monthly_revenue(property_id, tenant_id, month, year)

    if result is None:
        return None

    # Cache the result for 5 minutes
    await redis_client.setex(cache_key, 300, json.dumps(result))

    return result
