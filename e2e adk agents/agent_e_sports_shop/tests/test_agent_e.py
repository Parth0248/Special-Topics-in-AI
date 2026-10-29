"""Automated test suite for Agent E: Sports Shop Agent with AlloyDB & Local SQLite Fallback.

Tests:
1. Seamless SQLite fallback when AlloyDB is unreachable (zero exceptions)
2. Catalog seed data integrity (categories, 16 products, stores, inventory)
3. Vector similarity search ranking (cosine similarity top-k)
4. Category and price SQL filtering with vector search
5. Product details retrieval and spec validation
6. Multi-tier inventory check and low stock threshold warnings
7. Geospatial store discovery by postal code and city
8. Complete shopping cart lifecycle (add, view, remove, clear, taxes, shipping)
9. Order placement, atomic inventory decrement, and cart clearing
10. In-store pickup fulfillment and specific store stock decrement
11. Order placement validation (empty cart failure)
12. Inventory bounds checking (excess quantity failure)
13. Order status lookup and tracking verification
14. FastMCP tool registration and schema verification
15. Finn sports assistant conversational execution
"""

from __future__ import annotations


import pytest

from agent_e_sports_shop.agent import create_sports_agent
from agent_e_sports_shop.db import DatabaseManager
from agent_e_sports_shop.mcp_server import mcp
from agent_e_sports_shop.tools import (
    check_inventory,
    find_nearby_stores,
    get_order_status,
    get_product_details,
    manage_cart,
    place_order,
    search_products,
    set_db,
)
from agent_e_sports_shop.vector_store import (
    VectorStore,
    cosine_distance,
    cosine_similarity,
    deserialize_vector,
    serialize_vector,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Provides a fresh isolated SQLite database for each test to guarantee no side effects."""
    test_db_file = str(tmp_path / "test_sports_isolated.db")
    db = DatabaseManager(use_alloydb=False, db_path=test_db_file, auto_seed=True)
    set_db(db)
    yield db
    db.close()


def test_seamless_sqlite_fallback_when_alloydb_unreachable(tmp_path):
    """Verifies that an unreachable AlloyDB host probes and cleanly falls back to SQLite."""
    fallback_db_file = str(tmp_path / "fallback_probe.db")
    # Provide a non-routable IP to test connection probe timeout and clean recovery
    db = DatabaseManager(
        use_alloydb=True,
        alloydb_host="192.0.2.1",  # TEST-NET-1 non-routable IP per RFC 5737
        alloydb_port=5432,
        probe_timeout=0.2,
        db_path=fallback_db_file,
        auto_seed=True,
    )
    assert db.mode == "sqlite"
    assert db.sqlite_conn is not None

    # Verify search operates smoothly in fallback mode
    results = db.search_products("running shoes", limit=2)
    assert len(results) == 2
    assert "similarity_score" in results[0]
    db.close()


def test_seed_data_integrity(isolated_db):
    """Verifies that categories, 16 products, stores, and multi-tier inventory are seeded."""
    cur = isolated_db.sqlite_conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM categories")
    assert cur.fetchone()["count"] == 4

    cur.execute("SELECT COUNT(*) as count FROM products")
    assert cur.fetchone()["count"] == 16

    cur.execute("SELECT COUNT(*) as count FROM stores")
    assert cur.fetchone()["count"] == 4

    cur.execute("SELECT COUNT(*) as count FROM inventory")
    # 16 products * 5 locations (1 warehouse + 4 stores) = 80 inventory rows
    assert cur.fetchone()["count"] == 80


def test_vector_similarity_search_ranking():
    """Verifies vector search ranks relevant products at the top with descending scores."""
    # Query for trail running shoes
    results = search_products("breathable waterproof trail running shoes with rock plate", limit=4)
    assert len(results) > 0

    top_match = results[0]
    # Apex Trailblazer GTX should rank #1 for trail running
    assert top_match["product_id"] == "PROD-RUN-001"
    assert "Apex Trailblazer" in top_match["name"]
    assert top_match["similarity_score"] > 0.85

    # Verify descending similarity score order
    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_with_category_and_price_filters():
    """Verifies vector search combines with SQL category and max_price filters."""
    # Search for basketball items under $60
    results = search_products(query="basketball", category="basketball", max_price=60.0, limit=5)
    assert len(results) > 0

    for r in results:
        assert r["category_id"] == "basketball"
        assert r["price"] <= 60.0

    # The regulation basketball ($49.99) should be present
    pids = [r["product_id"] for r in results]
    assert "PROD-BSK-002" in pids


def test_get_product_details():
    """Verifies complete specifications and stock aggregation for a product."""
    details = get_product_details("PROD-RUN-001")
    assert "error" not in details
    assert details["product_id"] == "PROD-RUN-001"
    assert details["name"] == "Apex Trailblazer GTX Trail Running Shoes"
    assert "Vibram" in details["features"]
    assert details["price"] == 149.99
    assert details["rating"] == 4.8
    assert details["total_available_stock"] > 0
    assert details["in_stock"] is True

    # Test non-existent SKU returns clean error
    missing = get_product_details("PROD-INVALID-999")
    assert "error" in missing


def test_check_inventory_and_low_stock_warning():
    """Verifies store and warehouse stock checks and low-stock warning detection."""
    # Palo Alto store was seeded with low stock (2 units) on PROD-RUN-001 (threshold is 3)
    inv = check_inventory(product_id="PROD-RUN-001", store_id="STORE-PA-003")
    assert inv["product_id"] == "PROD-RUN-001"
    assert inv["store_stock"] == 2
    assert inv["low_stock_warning"] is True

    # San Jose store was seeded with 12 units on PROD-RUN-001 (threshold is 4)
    inv_sj = check_inventory(product_id="PROD-RUN-001", store_id="STORE-SJ-001")
    assert inv_sj["store_stock"] == 12
    assert inv_sj["low_stock_warning"] is False
    assert inv_sj["warehouse_stock"] == 45


def test_find_nearby_stores_geospatial():
    """Verifies store location retrieval and sorting by distance from zip code."""
    # Search nearby stores from San Jose postal code 95113
    stores = find_nearby_stores(postal_code="95113")
    assert len(stores) == 4
    # Closest should be Downtown San Jose Athletics (distance 0.0 mi)
    assert stores[0]["store_id"] == "STORE-SJ-001"
    assert stores[0]["distance_miles"] == 0.0

    # Filter by city
    sf_stores = find_nearby_stores(city="San Francisco")
    assert len(sf_stores) == 1
    assert sf_stores[0]["store_id"] == "STORE-SF-002"
    assert sf_stores[0]["city"] == "San Francisco"


def test_cart_lifecycle_add_view_remove_clear():
    """Tests complete cart management lifecycle."""
    user = "test_shopper_01"

    # 1. Initial cart view is empty
    empty_cart = manage_cart(action="view", user_id=user)
    assert empty_cart["item_count"] == 0
    assert empty_cart["subtotal"] == 0.0

    # 2. Add product (Alpine Rain Jacket, $199.99)
    res_add = manage_cart(action="add", user_id=user, product_id="PROD-OUT-001", quantity=1)
    assert "error" not in res_add
    assert res_add["item_count"] == 1
    assert res_add["subtotal"] == 199.99
    # Subtotal >= $75 -> Free shipping
    assert res_add["shipping"] == 0.0
    assert res_add["free_shipping_eligible"] is True

    # 3. Add second product (Jump Rope, $24.99)
    res_add2 = manage_cart(action="add", user_id=user, product_id="PROD-EQP-003", quantity=2)
    assert res_add2["item_count"] == 3
    expected_subtotal = 199.99 + (24.99 * 2)
    assert round(res_add2["subtotal"], 2) == round(expected_subtotal, 2)

    # 4. Remove 1 jump rope
    res_rem = manage_cart(action="remove", user_id=user, product_id="PROD-EQP-003", quantity=1)
    assert res_rem["item_count"] == 2

    # 5. Clear cart
    res_clear = manage_cart(action="clear", user_id=user)
    assert res_clear["item_count"] == 0
    assert len(res_clear["items"]) == 0


def test_place_order_and_inventory_decrement():
    """Verifies that placing an order decrements warehouse stock and clears the cart."""
    user = "test_shopper_02"
    pid = "PROD-RUN-002"  # CloudStrata Marathon Shoe

    # Initial warehouse stock
    init_inv = check_inventory(product_id=pid)
    init_wh_stock = init_inv["warehouse_stock"]

    # Add to cart
    manage_cart(action="add", user_id=user, product_id=pid, quantity=2)

    # Place order
    order = place_order(
        user_id=user,
        shipping_address="1 Washington Sq, San Jose, CA 95192",
        fulfillment_type="shipping",
    )
    assert "error" not in order
    assert order["status"] == "confirmed"
    assert order["order_id"].startswith("ORD-")
    assert order["tracking_number"].startswith("TRK-")
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 2

    # Check warehouse stock decremented by 2
    after_inv = check_inventory(product_id=pid)
    assert after_inv["warehouse_stock"] == init_wh_stock - 2

    # Check cart is now cleared
    cart_after = manage_cart(action="view", user_id=user)
    assert cart_after["item_count"] == 0


def test_place_order_in_store_pickup():
    """Verifies in-store pickup orders decrement specific store stock."""
    user = "test_shopper_pickup"
    pid = "PROD-BSK-001"
    store_id = "STORE-SJ-001"

    init_inv = check_inventory(product_id=pid, store_id=store_id)
    init_store_stock = init_inv["store_stock"]

    manage_cart(action="add", user_id=user, product_id=pid, quantity=1)

    order = place_order(
        user_id=user,
        fulfillment_type="in_store_pickup",
        pickup_store_id=store_id,
    )
    assert "error" not in order
    assert order["fulfillment_type"] == "in_store_pickup"
    assert order["pickup_store_id"] == store_id

    # Verify store inventory decremented
    after_inv = check_inventory(product_id=pid, store_id=store_id)
    assert after_inv["store_stock"] == init_store_stock - 1


def test_place_order_empty_cart_fails():
    """Verifies that placing an order with an empty cart returns an error."""
    order = place_order(user_id="empty_cart_user")
    assert "error" in order
    assert "Cart is empty" in order["error"]


def test_add_to_cart_excess_quantity_fails():
    """Verifies that adding more than network inventory fails gracefully."""
    res = manage_cart(action="add", user_id="greedy_shopper", product_id="PROD-RUN-001", quantity=99999)
    assert "error" in res
    assert "exceeds" in res["error"]


def test_order_status_tracking():
    """Verifies looking up an order by order_id returns items and confirmed status."""
    user = "test_status_user"
    manage_cart(action="add", user_id=user, product_id="PROD-OUT-003", quantity=1)
    placed = place_order(user_id=user, shipping_address="San Jose, CA")

    status = get_order_status(placed["order_id"])
    assert "error" not in status
    assert status["order_id"] == placed["order_id"]
    assert status["status"] == "confirmed"
    assert len(status["items"]) == 1

    # Check non-existent order
    bad = get_order_status("ORD-NONEXISTENT-0000")
    assert "error" in bad


def test_vector_math_primitives():
    """Directly verifies vector serialization and cosine distance/similarity primitives."""
    vs = VectorStore()
    v1 = vs.generate_embedding("trail running shoes")
    v2 = vs.generate_embedding("trail running shoes")
    v3 = vs.generate_embedding("rubber hex dumbbell weights")

    # Identical text produces identical unit vector
    assert cosine_similarity(v1, v2) == pytest.approx(1.0, abs=1e-4)
    assert cosine_distance(v1, v2) == pytest.approx(0.0, abs=1e-4)

    # Different categories produce significantly lower similarity
    diff_sim = cosine_similarity(v1, v3)
    assert diff_sim < 0.6

    # Test serialization round-trip
    blob = serialize_vector(v1)
    deser = deserialize_vector(blob)
    assert deser.shape == (768,)
    assert cosine_similarity(v1, deser) == pytest.approx(1.0, abs=1e-5)


def test_fastmcp_tool_registration():
    """Verifies that all 7 tools are registered in the FastMCP server."""
    # Verify mcp instance exists and has tool names
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    expected_tools = [
        "search_products_tool",
        "get_product_details_tool",
        "check_inventory_tool",
        "find_nearby_stores_tool",
        "manage_cart_tool",
        "place_order_tool",
        "get_order_status_tool",
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Expected tool {exp} not registered in FastMCP!"


def test_agent_conversational_turn():
    """Verifies Finn Sports Agent produces rich responses and handles conversational intents."""
    agent = create_sports_agent(user_id="convo_test_user")

    # Turn 1: Product recommendation query
    resp1 = agent.execute_turn("Find lightweight trail running shoes under $160")
    assert "Finn" in resp1 or "Apex Trailblazer" in resp1
    assert "149.99" in resp1

    # Turn 2: Add to cart
    resp2 = agent.execute_turn("Add to cart")
    assert "added" in resp2.lower() or "cart" in resp2.lower()

    # Turn 3: Checkout
    resp3 = agent.execute_turn("Place order")
    assert "order" in resp3.lower()
    assert "ORD-" in resp3
