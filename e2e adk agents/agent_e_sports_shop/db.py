"""Dual-mode DatabaseManager for Agent E: Sports Shop Agent.

Auto-probes live GCP AlloyDB with a 1.5-second connection timeout, seamlessly
falling back to local SQLite + NumPy cosine vector similarity search.
Ensures zero runtime errors when AlloyDB is unreachable.
"""

from __future__ import annotations

import datetime
import logging
import math
import os
import random
import socket
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple


try:
    from .seed_data import CATEGORIES, INVENTORY_SEED, PRODUCTS, STORES
    from .vector_store import (
        VectorStore,
        cosine_similarity,
        deserialize_vector,
        serialize_vector,
    )
except ImportError:
    from seed_data import CATEGORIES, INVENTORY_SEED, PRODUCTS, STORES
    from vector_store import (
        VectorStore,
        cosine_similarity,
        deserialize_vector,
        serialize_vector,
    )

logger = logging.getLogger("agent_e.db")


class DatabaseManager:
    """Manages sports catalog data, vector search, inventory, carts, and orders."""

    def __init__(
        self,
        use_alloydb: bool = False,
        alloydb_host: Optional[str] = None,
        alloydb_port: int = 5432,
        alloydb_database: str = "sports_shop",
        alloydb_user: str = "postgres",
        alloydb_password: Optional[str] = None,
        db_path: str = "sports_shop_local.db",
        probe_timeout: float = 1.5,
        auto_seed: bool = True,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.requested_alloydb = use_alloydb or bool(os.getenv("ALLOYDB_HOST"))
        self.alloydb_host = alloydb_host or os.getenv("ALLOYDB_HOST")
        self.alloydb_port = int(os.getenv("ALLOYDB_PORT", str(alloydb_port)))
        self.alloydb_database = alloydb_database or os.getenv("ALLOYDB_DATABASE", "sports_shop")
        self.alloydb_user = alloydb_user or os.getenv("ALLOYDB_USER", "postgres")
        self.alloydb_password = alloydb_password or os.getenv("ALLOYDB_PASSWORD", "")
        self.db_path = db_path
        self.probe_timeout = probe_timeout
        self.auto_seed = auto_seed
        self.vector_store = vector_store or VectorStore()

        self.mode = "sqlite"
        self._lock = threading.RLock()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self.pg_engine = None

        self._init_backend()

    def _init_backend(self) -> None:
        """Probes AlloyDB connectivity, falling back to SQLite on any error."""
        if self.requested_alloydb and self.alloydb_host:
            logger.info("Probing AlloyDB at %s:%s (timeout=%.1fs)...", self.alloydb_host, self.alloydb_port, self.probe_timeout)
            alloydb_ok = self._probe_alloydb_connection()
            if alloydb_ok:
                try:
                    self._init_alloydb()
                    self.mode = "alloydb"
                    print(f"[Agent E] Successfully connected to live GCP AlloyDB ({self.alloydb_host}:{self.alloydb_port}).")
                    return
                except Exception as exc:
                    logger.warning("[Agent E] AlloyDB initialization failed: %s. Falling back to local SQLite.", exc)

        # Seamless Fallback to SQLite + NumPy
        self.mode = "sqlite"
        print("[Agent E] Operating in LOCAL FALLBACK mode (SQLite + NumPy vector search).")
        self._init_sqlite()
        if self.auto_seed:
            self.seed_catalog()

    def _probe_alloydb_connection(self) -> bool:
        """Performs a fast non-blocking TCP socket probe to verify reachability."""
        if not self.alloydb_host:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.probe_timeout)
            result = sock.connect_ex((self.alloydb_host, self.alloydb_port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug("AlloyDB socket probe failed: %s", e)
            return False

    def _init_alloydb(self) -> None:
        """Initializes SQLAlchemy PostgreSQL connection pool for AlloyDB."""
        from sqlalchemy import create_engine
        conn_url = (
            f"postgresql+psycopg2://{self.alloydb_user}:{self.alloydb_password}"
            f"@{self.alloydb_host}:{self.alloydb_port}/{self.alloydb_database}"
        )
        self.pg_engine = create_engine(conn_url, connect_args={"connect_timeout": int(self.probe_timeout)})
        # Test connection execution
        with self.pg_engine.connect() as conn:
            conn.execute("SELECT 1")

    def _init_sqlite(self) -> None:
        """Initializes local SQLite database with required tables."""
        # Use check_same_thread=False for multi-threaded FastMCP/testing
        self.sqlite_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row

        with self.sqlite_conn:
            # 1. Categories
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    category_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT
                );
            """)

            # 2. Products
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    category_id TEXT REFERENCES categories(category_id),
                    name TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    description TEXT NOT NULL,
                    features TEXT,
                    rating REAL DEFAULT 4.5,
                    review_count INTEGER DEFAULT 0,
                    embedding BLOB
                );
            """)

            # 3. Stores
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    store_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    city TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    phone TEXT
                );
            """)

            # 4. Inventory
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    inventory_id TEXT PRIMARY KEY,
                    product_id TEXT REFERENCES products(product_id),
                    store_id TEXT,
                    stock_quantity INTEGER NOT NULL DEFAULT 0,
                    low_stock_threshold INTEGER DEFAULT 5
                );
            """)

            # 5. Carts & Cart Items
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS carts (
                    cart_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)

            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS cart_items (
                    item_id TEXT PRIMARY KEY,
                    cart_id TEXT REFERENCES carts(cart_id),
                    product_id TEXT REFERENCES products(product_id),
                    quantity INTEGER NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL
                );
            """)

            # 6. Orders & Order Items
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    fulfillment_type TEXT NOT NULL,
                    shipping_address TEXT,
                    pickup_store_id TEXT REFERENCES stores(store_id),
                    created_at TEXT
                );
            """)

            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    order_item_id TEXT PRIMARY KEY,
                    order_id TEXT REFERENCES orders(order_id),
                    product_id TEXT REFERENCES products(product_id),
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL
                );
            """)

    def seed_catalog(self) -> None:
        """Seeds categories, products, stores, and inventory with pre-computed vectors."""
        with self._lock:
            cur = self.sqlite_conn.cursor()
            # Check if already seeded
            cur.execute("SELECT COUNT(*) AS count FROM products")
            if cur.fetchone()["count"] >= len(PRODUCTS):
                return

            logger.info("Seeding synthetic sports catalog into local SQLite database...")

            # 1. Categories
            for cat in CATEGORIES:
                cur.execute(
                    "INSERT OR REPLACE INTO categories (category_id, name, description) VALUES (?, ?, ?)",
                    (cat["category_id"], cat["name"], cat["description"]),
                )

            # 2. Products with 768-d unit embeddings
            for prod in PRODUCTS:
                embed_text = f"{prod['name']} {prod['brand']} {prod['category_id']} {prod['description']} {prod['features']}"
                vec = self.vector_store.generate_embedding(embed_text)
                blob = serialize_vector(vec)

                cur.execute(
                    """
                    INSERT OR REPLACE INTO products (
                        product_id, category_id, name, brand, price, currency,
                        description, features, rating, review_count, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prod["product_id"],
                        prod["category_id"],
                        prod["name"],
                        prod["brand"],
                        prod["price"],
                        prod["currency"],
                        prod["description"],
                        prod["features"],
                        prod["rating"],
                        prod["review_count"],
                        blob,
                    ),
                )

            # 3. Stores
            for store in STORES:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO stores (
                        store_id, name, address, city, postal_code, latitude, longitude, phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        store["store_id"],
                        store["name"],
                        store["address"],
                        store["city"],
                        store["postal_code"],
                        store["latitude"],
                        store["longitude"],
                        store["phone"],
                    ),
                )

            # 4. Inventory
            for inv in INVENTORY_SEED:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO inventory (
                        inventory_id, product_id, store_id, stock_quantity, low_stock_threshold
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        inv["inventory_id"],
                        inv["product_id"],
                        inv["store_id"],
                        inv["stock_quantity"],
                        inv["low_stock_threshold"],
                    ),
                )

            self.sqlite_conn.commit()
            logger.info("Catalog seeding completed successfully.")

    # =========================================================================
    # 1. Search Products (Vector Similarity + SQL Filters)
    # =========================================================================

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Searches products using vector cosine similarity ranking and optional SQL filters."""
        query_vec = self.vector_store.generate_embedding(query)

        # Build candidate filter query
        sql = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if category:
            cat_clean = category.strip().lower()
            sql += " AND (LOWER(category_id) = ? OR LOWER(category_id) LIKE ?)"
            params.extend([cat_clean, f"%{cat_clean}%"])

        if max_price is not None and max_price > 0:
            sql += " AND price <= ?"
            params.append(float(max_price))

        with self._lock:
            cur = self.sqlite_conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()

        if not rows:
            return []

        # Compute cosine similarity ranking
        scored: List[Tuple[Dict[str, Any], float]] = []
        for r in rows:
            item = dict(r)
            blob = item.pop("embedding", None)
            if blob:
                vec = deserialize_vector(blob)
                score = cosine_similarity(query_vec, vec)
            else:
                score = 0.0

            item["similarity_score"] = round(float(score), 4)
            scored.append((item, score))

        # Sort descending by similarity score
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:limit]]

    # =========================================================================
    # 2. Get Product Details
    # =========================================================================

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Retrieves complete specifications, category details, and stock summary."""
        with self._lock:
            cur = self.sqlite_conn.cursor()
            cur.execute(
                """
                SELECT p.*, c.name as category_name
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.category_id
                WHERE p.product_id = ?
                """,
                (product_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"error": f"Product '{product_id}' not found"}

            prod = dict(row)
            prod.pop("embedding", None)

            # Get aggregated inventory
            cur.execute(
                """
                SELECT store_id, stock_quantity, low_stock_threshold
                FROM inventory
                WHERE product_id = ?
                """,
                (product_id,),
            )
            inv_rows = cur.fetchall()

            total_stock = 0
            warehouse_stock = 0
            store_stock: Dict[str, int] = {}

            for inv in inv_rows:
                s_id = inv["store_id"]
                qty = inv["stock_quantity"]
                total_stock += qty
                if s_id == "WAREHOUSE-CENTRAL":
                    warehouse_stock = qty
                else:
                    store_stock[s_id] = qty

            prod["total_available_stock"] = total_stock
            prod["warehouse_stock"] = warehouse_stock
            prod["store_stock_breakdown"] = store_stock
            prod["in_stock"] = total_stock > 0

            return prod

    # =========================================================================
    # 3. Check Inventory
    # =========================================================================

    def check_inventory(
        self,
        product_id: str,
        store_id: Optional[str] = None,
        postal_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Checks available stock for a product at a local store or central warehouse."""
        with self._lock:
            cur = self.sqlite_conn.cursor()
            # Validate product exists
            cur.execute("SELECT name FROM products WHERE product_id = ?", (product_id,))
            p_row = cur.fetchone()
            if not p_row:
                return {"error": f"Product '{product_id}' not found"}

            product_name = p_row["name"]

            # If postal code provided but no store_id, resolve nearest store
            target_store_id = store_id
            target_store_name = None
            if not target_store_id and postal_code:
                nearby = self.find_nearby_stores(postal_code=postal_code)
                if nearby:
                    target_store_id = nearby[0]["store_id"]
                    target_store_name = nearby[0]["name"]

            # Fetch inventory rows
            cur.execute("SELECT * FROM inventory WHERE product_id = ?", (product_id,))
            inv_rows = cur.fetchall()

            location_stock = None
            low_stock_warning = False
            warehouse_stock = 0
            total_stock = 0

            for inv in inv_rows:
                s_id = inv["store_id"]
                qty = inv["stock_quantity"]
                thresh = inv["low_stock_threshold"]
                total_stock += qty

                if s_id == "WAREHOUSE-CENTRAL":
                    warehouse_stock = qty

                if target_store_id and s_id == target_store_id:
                    location_stock = qty
                    if qty <= thresh:
                        low_stock_warning = True

            return {
                "product_id": product_id,
                "product_name": product_name,
                "store_id": target_store_id,
                "store_name": target_store_name,
                "store_stock": location_stock,
                "warehouse_stock": warehouse_stock,
                "total_network_stock": total_stock,
                "in_stock": (location_stock if location_stock is not None else total_stock) > 0,
                "low_stock_warning": low_stock_warning,
            }

    # =========================================================================
    # 4. Find Nearby Stores
    # =========================================================================

    def find_nearby_stores(
        self,
        postal_code: Optional[str] = None,
        city: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Finds retail stores filtered by city or sorted by proximity to postal code."""
        with self._lock:
            cur = self.sqlite_conn.cursor()
            cur.execute("SELECT * FROM stores")
            stores = [dict(r) for r in cur.fetchall()]

        if not stores:
            return []

        # Approximate reference coordinates for common Northern CA zip codes
        POSTAL_COORDS = {
            "95113": (37.3344, -121.8893),  # San Jose
            "95192": (37.3352, -121.8811),  # SJSU
            "94102": (37.7845, -122.4070),  # SF
            "94304": (37.4435, -122.1712),  # Palo Alto
            "94611": (37.8205, -122.2589),  # Oakland
        }

        def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            r = 3958.8  # Earth radius in miles
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return r * c

        if city:
            c_low = city.strip().lower()
            stores = [s for s in stores if c_low in s["city"].lower()]

        if postal_code:
            p_clean = postal_code.strip()
            if p_clean in POSTAL_COORDS:
                ref_lat, ref_lon = POSTAL_COORDS[p_clean]
                for s in stores:
                    dist = haversine_miles(ref_lat, ref_lon, s["latitude"], s["longitude"])
                    s["distance_miles"] = round(dist, 1)
            else:
                warning_msg = "Postal code outside local store service area; showing closest regional hubs."
                ref_lat, ref_lon = (37.3352, -121.8811)
                for s in stores:
                    dist = haversine_miles(ref_lat, ref_lon, s["latitude"], s["longitude"])
                    s["distance_miles"] = round(dist, 1)
                    s["warning"] = warning_msg
            stores.sort(key=lambda s: s.get("distance_miles", 999.0))

        return stores

    # =========================================================================
    # 5. Manage Cart
    # =========================================================================

    def manage_cart(
        self,
        action: str,
        user_id: str,
        product_id: Optional[str] = None,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Manages shopping cart operations: 'view', 'add', 'remove', 'clear'."""
        action_clean = action.strip().lower()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if action_clean in ("add", "remove"):
            if not isinstance(quantity, int) or quantity <= 0:
                return {"error": "Quantity must be a positive integer greater than zero."}

        with self._lock:
            cur = self.sqlite_conn.cursor()

            # Ensure cart exists for user
            cur.execute("SELECT cart_id FROM carts WHERE user_id = ?", (user_id,))
            cart_row = cur.fetchone()
            if not cart_row:
                cart_id = f"CART-{user_id}"
                cur.execute(
                    "INSERT INTO carts (cart_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (cart_id, user_id, now_str, now_str),
                )
                self.sqlite_conn.commit()
            else:
                cart_id = cart_row["cart_id"]

            if action_clean == "add":
                if not product_id:
                    return {"error": "product_id is required for 'add' action"}

                cur.execute("SELECT name, price FROM products WHERE product_id = ?", (product_id,))
                prod = cur.fetchone()
                if not prod:
                    return {"error": f"Product '{product_id}' does not exist"}

                unit_price = prod["price"]

                # Check available network inventory
                cur.execute("SELECT SUM(stock_quantity) as total FROM inventory WHERE product_id = ?", (product_id,))
                stock_res = cur.fetchone()
                total_stock = stock_res["total"] if stock_res and stock_res["total"] is not None else 0

                # Check existing quantity in cart
                cur.execute("SELECT item_id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
                item_row = cur.fetchone()
                current_qty = item_row["quantity"] if item_row else 0
                new_qty = current_qty + quantity

                if new_qty > total_stock:
                    return {
                        "error": f"Requested quantity ({new_qty}) exceeds total available inventory ({total_stock}).",
                        "available_inventory": total_stock,
                    }

                if item_row:
                    cur.execute(
                        "UPDATE cart_items SET quantity = ?, unit_price = ? WHERE item_id = ?",
                        (new_qty, unit_price, item_row["item_id"]),
                    )
                else:
                    item_id = f"ITEM-{cart_id}-{product_id}"
                    cur.execute(
                        "INSERT INTO cart_items (item_id, cart_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                        (item_id, cart_id, product_id, quantity, unit_price),
                    )

                cur.execute("UPDATE carts SET updated_at = ? WHERE cart_id = ?", (now_str, cart_id))
                self.sqlite_conn.commit()

            elif action_clean == "remove":
                if not product_id:
                    return {"error": "product_id is required for 'remove' action"}

                cur.execute("SELECT item_id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
                item_row = cur.fetchone()
                if item_row:
                    new_qty = item_row["quantity"] - quantity
                    if new_qty <= 0:
                        cur.execute("DELETE FROM cart_items WHERE item_id = ?", (item_row["item_id"],))
                    else:
                        cur.execute("UPDATE cart_items SET quantity = ? WHERE item_id = ?", (new_qty, item_row["item_id"]))
                    cur.execute("UPDATE carts SET updated_at = ? WHERE cart_id = ?", (now_str, cart_id))
                    self.sqlite_conn.commit()

            elif action_clean == "clear":
                cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
                cur.execute("UPDATE carts SET updated_at = ? WHERE cart_id = ?", (now_str, cart_id))
                self.sqlite_conn.commit()

            elif action_clean != "view":
                return {"error": f"Unknown cart action '{action}'. Valid actions: view, add, remove, clear."}

            # Return cart breakdown
            cur.execute(
                """
                SELECT ci.product_id, p.name, ci.quantity, ci.unit_price, (ci.quantity * ci.unit_price) as line_total
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.product_id
                WHERE ci.cart_id = ?
                """,
                (cart_id,),
            )
            items = [dict(r) for r in cur.fetchall()]

            subtotal = sum(item["line_total"] for item in items)
            tax = round(subtotal * 0.085, 2)  # 8.5% sales tax
            shipping = 0.0 if (subtotal >= 75.0 or subtotal == 0.0) else 7.99
            total = round(subtotal + tax + shipping, 2)

            return {
                "cart_id": cart_id,
                "user_id": user_id,
                "items": items,
                "item_count": sum(item["quantity"] for item in items),
                "subtotal": round(subtotal, 2),
                "tax": tax,
                "shipping": shipping,
                "total_amount": total,
                "currency": "USD",
                "free_shipping_eligible": subtotal >= 75.0,
            }

    # =========================================================================
    # 6. Place Order (Atomic Inventory Decrement & Cart Clear)
    # =========================================================================

    def place_order(
        self,
        user_id: str,
        shipping_address: Optional[str] = None,
        fulfillment_type: str = "shipping",
        pickup_store_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Places an order, decrements store or warehouse inventory, and clears the cart."""
        with self._lock:
            cur = self.sqlite_conn.cursor()

            # Retrieve user cart
            cart = self.manage_cart("view", user_id=user_id)
            items = cart.get("items", [])
            if not items:
                return {"error": "Cart is empty. Add products before placing an order."}

            for item in items:
                if not isinstance(item.get("quantity"), int) or item.get("quantity", 0) <= 0:
                    return {
                        "error": f"Invalid item quantity ({item.get('quantity')}) for product '{item.get('name', item.get('product_id'))}'. Quantity must be a positive integer greater than zero."
                    }

            if fulfillment_type == "in_store_pickup":
                if not pickup_store_id:
                    return {"error": "pickup_store_id is required for in-store pickup orders."}
            else:
                fulfillment_type = "shipping"
                if not shipping_address:
                    shipping_address = "Standard Delivery Address on File"

            now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
            order_num = random.randint(1000, 9999)
            date_prefix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
            order_id = f"ORD-{date_prefix}-{order_num}"

            # Validate and decrement inventory inside an atomic SQLite transaction
            try:
                for item in items:
                    pid = item["product_id"]
                    req_qty = item["quantity"]

                    if fulfillment_type == "in_store_pickup":
                        cur.execute(
                            "SELECT stock_quantity FROM inventory WHERE product_id = ? AND store_id = ?",
                            (pid, pickup_store_id),
                        )
                        inv_row = cur.fetchone()
                        if not inv_row or inv_row["stock_quantity"] < req_qty:
                            avail = inv_row["stock_quantity"] if inv_row else 0
                            raise ValueError(
                                f"Insufficient stock for {item['name']} at store {pickup_store_id} "
                                f"(requested {req_qty}, available {avail})."
                            )
                        cur.execute(
                            "UPDATE inventory SET stock_quantity = stock_quantity - ? WHERE product_id = ? AND store_id = ?",
                            (req_qty, pid, pickup_store_id),
                        )
                    else:
                        # Shipping fulfillment: deduct from warehouse first, then any store
                        cur.execute(
                            "SELECT inventory_id, stock_quantity FROM inventory WHERE product_id = ? AND store_id = 'WAREHOUSE-CENTRAL'",
                            (pid,),
                        )
                        wh_row = cur.fetchone()
                        if wh_row and wh_row["stock_quantity"] >= req_qty:
                            cur.execute(
                                "UPDATE inventory SET stock_quantity = stock_quantity - ? WHERE inventory_id = ?",
                                (req_qty, wh_row["inventory_id"]),
                            )
                        else:
                            # Deduct across available inventory
                            cur.execute(
                                "SELECT inventory_id, stock_quantity FROM inventory WHERE product_id = ? AND stock_quantity > 0 ORDER BY stock_quantity DESC",
                                (pid,),
                            )
                            avail_rows = cur.fetchall()
                            rem = req_qty
                            for a_row in avail_rows:
                                deduct = min(rem, a_row["stock_quantity"])
                                cur.execute(
                                    "UPDATE inventory SET stock_quantity = stock_quantity - ? WHERE inventory_id = ?",
                                    (deduct, a_row["inventory_id"]),
                                )
                                rem -= deduct
                                if rem <= 0:
                                    break
                            if rem > 0:
                                raise ValueError(f"Insufficient network inventory for {item['name']}.")

                # Insert Order Record
                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id, user_id, total_amount, status, fulfillment_type, shipping_address, pickup_store_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        user_id,
                        cart["total_amount"],
                        "confirmed",
                        fulfillment_type,
                        shipping_address,
                        pickup_store_id,
                        now_str,
                    ),
                )

                # Insert Order Items
                for item in items:
                    order_item_id = f"OITEM-{order_id}-{item['product_id']}"
                    cur.execute(
                        """
                        INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (order_item_id, order_id, item["product_id"], item["quantity"], item["unit_price"]),
                    )

                # Clear cart
                cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart["cart_id"],))
                self.sqlite_conn.commit()

            except Exception as e:
                self.sqlite_conn.rollback()
                return {"error": f"Order placement failed: {str(e)}"}

            return {
                "order_id": order_id,
                "status": "confirmed",
                "fulfillment_type": fulfillment_type,
                "items": items,
                "subtotal": cart["subtotal"],
                "tax": cart["tax"],
                "shipping": cart["shipping"],
                "total_amount": cart["total_amount"],
                "currency": "USD",
                "shipping_address": shipping_address if fulfillment_type == "shipping" else None,
                "pickup_store_id": pickup_store_id if fulfillment_type == "in_store_pickup" else None,
                "estimated_delivery": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
                "tracking_number": f"TRK-{random.randint(10000000, 99999999)}",
            }

    # =========================================================================
    # 7. Get Order Status
    # =========================================================================

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Retrieves order tracking, item breakdown, and delivery status."""
        with self._lock:
            cur = self.sqlite_conn.cursor()
            cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            order_row = cur.fetchone()
            if not order_row:
                return {"error": f"Order '{order_id}' not found"}

            order = dict(order_row)
            cur.execute(
                """
                SELECT oi.product_id, p.name, oi.quantity, oi.unit_price, (oi.quantity * oi.unit_price) as line_total
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE oi.order_id = ?
                """,
                (order_id,),
            )
            order["items"] = [dict(r) for r in cur.fetchall()]
            return order

    def close(self) -> None:
        """Closes all database connections cleanly."""
        if self.sqlite_conn:
            try:
                self.sqlite_conn.close()
            except Exception:
                pass
            self.sqlite_conn = None
