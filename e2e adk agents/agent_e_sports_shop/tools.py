"""Core E-Commerce sports shop tools for Agent E.

Exposes 7 standard tools used by the ADK agent, FastMCP server, and test suites:
1. search_products
2. get_product_details
3. check_inventory
4. find_nearby_stores
5. manage_cart
6. place_order
7. get_order_status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from .db import DatabaseManager
except ImportError:
    from db import DatabaseManager

_DEFAULT_DB: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Returns the singleton DatabaseManager instance, initializing it if needed."""
    global _DEFAULT_DB
    if _DEFAULT_DB is None:
        _DEFAULT_DB = DatabaseManager()
    return _DEFAULT_DB


def set_db(db: DatabaseManager) -> None:
    """Overrides the global DatabaseManager instance (useful for isolated tests)."""
    global _DEFAULT_DB
    _DEFAULT_DB = db


def search_products(
    query: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Searches the sports shop catalog using vector similarity and optional filters.

    Args:
        query: Free-form text query (e.g. 'trail running shoes for rocky trails').
        category: Optional category filter ('running', 'basketball', 'outdoor', 'equipment').
        max_price: Optional maximum price ceiling in USD.
        limit: Maximum number of products to return (default 5).

    Returns:
        List of product records with similarity_score, price, description, and specs.
    """
    db = get_db()
    return db.search_products(query=query, category=category, max_price=max_price, limit=limit)


def get_product_details(product_id: str) -> Dict[str, Any]:
    """Retrieves comprehensive specifications, ratings, and stock status for a product.

    Args:
        product_id: Product SKU / identifier (e.g. 'PROD-RUN-001').

    Returns:
        Product details dictionary with full features and aggregated inventory breakdown.
    """
    db = get_db()
    return db.get_product_details(product_id=product_id)


def check_inventory(
    product_id: str,
    store_id: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Checks stock availability for a product at a local retail store or warehouse.

    Args:
        product_id: Product SKU (e.g. 'PROD-RUN-001').
        store_id: Optional specific store identifier (e.g. 'STORE-SJ-001').
        postal_code: Optional customer postal code (e.g. '95113') to check closest store.

    Returns:
        Inventory summary showing store stock, warehouse stock, and low stock warnings.
    """
    db = get_db()
    return db.check_inventory(product_id=product_id, store_id=store_id, postal_code=postal_code)


def find_nearby_stores(
    postal_code: Optional[str] = None,
    city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Finds physical sports retail stores filtered by city or sorted by proximity to postal code.

    Args:
        postal_code: Optional zip code to calculate distance in miles.
        city: Optional city name filter (e.g. 'San Jose', 'San Francisco').

    Returns:
        List of retail stores with address, phone number, and distance.
    """
    db = get_db()
    return db.find_nearby_stores(postal_code=postal_code, city=city)


def manage_cart(
    action: str,
    user_id: str,
    product_id: Optional[str] = None,
    quantity: int = 1,
) -> Dict[str, Any]:
    """Manages the customer's active shopping cart.

    Args:
        action: Cart action: 'view', 'add', 'remove', or 'clear'.
        user_id: Customer or session identifier.
        product_id: Product SKU (required for 'add' and 'remove').
        quantity: Number of units to add or remove (default 1).

    Returns:
        Cart summary with line items, subtotal, tax, shipping, and total amount.
    """
    db = get_db()
    return db.manage_cart(action=action, user_id=user_id, product_id=product_id, quantity=quantity)


def place_order(
    user_id: str,
    shipping_address: Optional[str] = None,
    fulfillment_type: str = "shipping",
    pickup_store_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Checks out the customer's current cart and places a confirmed order.

    Decrements real inventory and clears the user's cart in an atomic transaction.

    Args:
        user_id: Customer or session identifier.
        shipping_address: Destination shipping address (for standard delivery).
        fulfillment_type: 'shipping' or 'in_store_pickup'.
        pickup_store_id: Retail store ID (required if fulfillment_type is 'in_store_pickup').

    Returns:
        Confirmed order receipt with order ID, tracking number, items, and total amount.
    """
    db = get_db()
    return db.place_order(
        user_id=user_id,
        shipping_address=shipping_address,
        fulfillment_type=fulfillment_type,
        pickup_store_id=pickup_store_id,
    )


def get_order_status(order_id: str) -> Dict[str, Any]:
    """Retrieves tracking information and fulfillment status for an existing order.

    Args:
        order_id: The order confirmation ID (e.g. 'ORD-20261029-1234').

    Returns:
        Order status dictionary including line items, delivery type, and current status.
    """
    db = get_db()
    return db.get_order_status(order_id=order_id)


ALL_TOOLS = [
    search_products,
    get_product_details,
    check_inventory,
    find_nearby_stores,
    manage_cart,
    place_order,
    get_order_status,
]
