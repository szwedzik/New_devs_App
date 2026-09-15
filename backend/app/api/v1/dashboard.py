from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant is associated with this account")

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except Exception as e:
        # Revenue figures must never be guessed at, so a broken lookup fails loudly.
        logger.error(f"Revenue lookup failed for {property_id} (tenant: {tenant_id}): {e}")
        raise HTTPException(status_code=503, detail="Revenue data is temporarily unavailable")

    if revenue_data is None:
        raise HTTPException(status_code=404, detail="Property not found")

    total_revenue_float = float(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
