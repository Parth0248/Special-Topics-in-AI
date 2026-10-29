"""FastMCP Server for Agent E: Sports Shop Agent.

Exposes the 7 sports shop catalog and order management tools over the
Model Context Protocol (MCP) using FastMCP.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

try:
    from .tools import (
        check_inventory,
        find_nearby_stores,
        get_order_status,
        get_product_details,
        manage_cart,
        place_order,
        search_products,
    )
except ImportError:
    from tools import (
        check_inventory,
        find_nearby_stores,
        get_order_status,
        get_product_details,
        manage_cart,
        place_order,
        search_products,
    )

logger = logging.getLogger("agent_e.mcp_server")

# Initialize FastMCP Server
mcp = FastMCP("SportsShopServer")


@mcp.tool()
def search_products_tool(
    query: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Search products in the sports catalog using vector similarity and optional filters."""
    return search_products(query=query, category=category, max_price=max_price, limit=limit)


@mcp.tool()
def get_product_details_tool(product_id: str) -> Dict[str, Any]:
    """Retrieve detailed product specifications, features, and stock availability."""
    return get_product_details(product_id=product_id)


@mcp.tool()
def check_inventory_tool(
    product_id: str,
    store_id: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Check stock availability at a specific store, nearest store, or central warehouse."""
    return check_inventory(product_id=product_id, store_id=store_id, postal_code=postal_code)


@mcp.tool()
def find_nearby_stores_tool(
    postal_code: Optional[str] = None,
    city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Find sports retail store locations filtered by city or sorted by proximity to postal code."""
    return find_nearby_stores(postal_code=postal_code, city=city)


@mcp.tool()
def manage_cart_tool(
    action: str,
    user_id: str,
    product_id: Optional[str] = None,
    quantity: int = 1,
) -> Dict[str, Any]:
    """Manage customer shopping cart: view items, add products, remove products, or clear cart."""
    return manage_cart(action=action, user_id=user_id, product_id=product_id, quantity=quantity)


@mcp.tool()
def place_order_tool(
    user_id: str,
    shipping_address: Optional[str] = None,
    fulfillment_type: str = "shipping",
    pickup_store_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Place an order for all items in the user's cart and decrement store/warehouse stock."""
    return place_order(
        user_id=user_id,
        shipping_address=shipping_address,
        fulfillment_type=fulfillment_type,
        pickup_store_id=pickup_store_id,
    )


@mcp.tool()
def get_order_status_tool(order_id: str) -> Dict[str, Any]:
    """Retrieve status, line items, and tracking details for a previously placed order."""
    return get_order_status(order_id=order_id)


def run_server() -> None:
    """Runs the FastMCP server over standard I/O."""
    mcp.run()


if __name__ == "__main__":
    run_server()
