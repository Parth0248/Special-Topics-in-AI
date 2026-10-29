# Agent E: E-Commerce Sports Shop Agent with AlloyDB & Local SQLite Vector Fallback

A production-grade conversational e-commerce sports assistant (**"Finn"**) built using the **Google Agent Development Kit (ADK)** and the **Model Context Protocol (MCP)**. Modeled after the Google Cloud reference architecture (*sports-agent-adk-mcp-alloydb*), Agent E delivers semantic product discovery, vector similarity search, multi-tier inventory verification, cart management, and atomic order checkout.

---

## 1. System Architecture & Dual-Mode Auto-Sensing

Agent E features a resilient **dual-mode database manager** (`db.py`). In cloud environments, it connects to **Google Cloud AlloyDB for PostgreSQL** with `pgvector`. In local development, CI/CD, and offline testing environments, it automatically senses that AlloyDB is unreachable (via a 1.5-second non-blocking TCP probe) and falls back seamlessly to **local SQLite with NumPy vector cosine similarity search**, guaranteeing zero crashes and zero configuration friction.

```
+-----------------------------------------------------------------------------------+
|                           Customer / CLI Interaction                              |
|                (--interactive / --query / --demo / MCP Client)                    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        ADK Conversational Agent ("Finn")                         |
|     (Gemini 2.5 Flash Function Calling / Deterministic Offline Reasoning Loop)    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             7 FastMCP E-Commerce Tools                            |
| search_products | get_product_details | check_inventory | find_nearby_stores      |
| manage_cart     | place_order         | get_order_status                          |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        Dual-Mode DatabaseManager (db.py)                          |
|                  Auto-Probing Probe Timeout: 1.5 Seconds                          |
+-----------------------------------------------------------------------------------+
                   |                                             |
     [AlloyDB Reachable]                           [AlloyDB Unreachable]
                   |                                             |
                   v                                             v
+-------------------------------------+       +-------------------------------------+
|   Google Cloud AlloyDB Backend      |       |     Local SQLite Fallback Backend   |
|   - PostgreSQL + pgvector           |       |     - SQLite3 storage               |
|   - Vector operator: <=>            |       |     - 768-d Float32 BLOB embeddings |
|   - PostGIS store distance          |       |     - NumPy vectorized cosine search|
|   - Multi-AZ enterprise replication |       |     - Zero external dependencies    |
+-------------------------------------+       +-------------------------------------+
```

---

## 2. FastMCP Tool Inventory

Agent E exposes 7 strictly-typed FastMCP tools via `mcp_server.py` and direct Python callables via `tools.py`:

| # | Tool Name | Parameters | Description |
|---|-----------|------------|-------------|
| 1 | `search_products` | `query: str`, `category: str?`, `max_price: float?`, `limit: int = 5` | Performs 768-d vector cosine similarity ranking combined with optional SQL category and budget constraints. |
| 2 | `get_product_details` | `product_id: str` | Retrieves full technical specifications, Gore-Tex/Vibram features, ratings, and network inventory breakdown. |
| 3 | `check_inventory` | `product_id: str`, `store_id: str?`, `postal_code: str?` | Inspects real-time stock at central warehouse and retail locations; triggers low-stock threshold alerts. |
| 4 | `find_nearby_stores` | `postal_code: str?`, `city: str?` | Locates retail stores, calculates haversine distance in miles from customer zip code, and returns store contacts. |
| 5 | `manage_cart` | `action: str`, `user_id: str`, `product_id: str?`, `quantity: int = 1` | Handles cart operations (`view`, `add`, `remove`, `clear`), enforces inventory stock limits, and calculates taxes (8.5%) and free shipping ($75 threshold). |
| 6 | `place_order` | `user_id: str`, `shipping_address: str?`, `fulfillment_type: str`, `pickup_store_id: str?` | Atomically validates stock, decrements inventory (warehouse or store pickup), creates order, and clears cart. |
| 7 | `get_order_status` | `order_id: str` | Retrieves live order tracking, status (`CONFIRMED`, `PROCESSING`, `SHIPPED`), and purchased line items. |

---

## 3. Database Schema

The database maintains 8 relational tables with 768-dimensional vector embeddings:

```sql
-- 1. Categories
CREATE TABLE categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

-- 2. Products (768-d Vector Embeddings)
CREATE TABLE products (
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
    embedding BLOB -- In AlloyDB: VECTOR(768); In SQLite: 768-float BLOB
);

-- 3. Retail Stores
CREATE TABLE stores (
    store_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    phone TEXT
);

-- 4. Multi-Tier Inventory (Warehouse + Retail Stores)
CREATE TABLE inventory (
    inventory_id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(product_id),
    store_id TEXT, -- 'WAREHOUSE-CENTRAL' or store_id
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    low_stock_threshold INTEGER DEFAULT 5
);

-- 5. Carts & Cart Items
CREATE TABLE carts (
    cart_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE cart_items (
    item_id TEXT PRIMARY KEY,
    cart_id TEXT REFERENCES carts(cart_id),
    product_id TEXT REFERENCES products(product_id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL
);

-- 6. Orders & Order Items
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    fulfillment_type TEXT NOT NULL,
    shipping_address TEXT,
    pickup_store_id TEXT REFERENCES stores(store_id),
    created_at TEXT
);

CREATE TABLE order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT REFERENCES orders(order_id),
    product_id TEXT REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
```

---

## 4. Installation & Setup

Per project standards, all execution runs inside an isolated Python virtual environment (`.venv`):

```bash
# Navigate to Agent E directory
cd "e2e adk agents/agent_e_sports_shop"

# Create virtual environment (.venv)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 5. Environment Configuration

Copy the example configuration file:

```bash
cp .env.example .env
```

Configuration variables (`.env`):
```ini
# Google Gemini API (Required for live Gemini models)
# If omitted, Agent E operates in deterministic offline assistant mode
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=text-embedding-004

# AlloyDB Live Database Connection (Optional)
# If unreachable, Agent E auto-detects and switches to SQLite + NumPy
ALLOYDB_HOST=10.0.0.1
ALLOYDB_PORT=5432
ALLOYDB_DATABASE=sports_shop
ALLOYDB_USER=postgres
ALLOYDB_PASSWORD=your_secure_password
ALLOYDB_SSL_MODE=require

# Local Database
LOCAL_DB_PATH=sports_shop_local.db
```

---

## 6. Execution Modes

### Mode A: Automated End-to-End Demonstration (`--demo`)
Executes an automated, 8-step customer journey through vector search, product dossier retrieval, inventory check, nearby store lookup, cart add, tax/shipping calculation, order placement, and tracking verification:

```bash
python -m agent_e_sports_shop.main --demo
```

### Mode B: Interactive Conversational Shopping (`--interactive`)
Launches an interactive chat loop with **Finn**, the sports advisor:

```bash
python -m agent_e_sports_shop.main --interactive
```

Example interaction:
```
You > Find lightweight trail running shoes under $160
Finn > Hey! Finn here. Based on our vector similarity search, here are top picks tailored for you:
       🏅 Apex Trailblazer GTX Trail Running Shoes — $149.99 (Score: 0.95 | Rating: 4.8★)
          Rugged waterproof trail running shoes with Gore-Tex membrane and Vibram Megagrip.

You > Add to cart
Finn > Awesome choice! I've added Apex Trailblazer GTX Trail Running Shoes to your cart. 🛒
       Current Cart Total: $162.74 (Free Shipping Unlocked! 🚀)

You > Checkout
Finn > Boom! Your order has been placed successfully! 🎉
       Order ID: ORD-20261029-4821 | Tracking Number: TRK-59201948
```

### Mode C: Single Query Execution (`--query`)
```bash
python -m agent_e_sports_shop.main --query "Check stock for Apex Trailblazer in San Jose"
```

### Mode D: FastMCP Stdio Server
Run Agent E as a standard Model Context Protocol server:
```bash
python -m agent_e_sports_shop.mcp_server
```

---

## 7. Automated Test Verification

Execute the complete 16-test suite verifying vector ranking, cart state transitions, inventory decrements, and AlloyDB fallback:

```bash
pytest -o pythonpath=. --basetemp=.pytest_tmp tests/ -v
```

Expected output:
```
tests/test_agent_e.py::test_seamless_sqlite_fallback_when_alloydb_unreachable PASSED [  6%]
tests/test_agent_e.py::test_seed_data_integrity PASSED                   [ 12%]
tests/test_agent_e.py::test_vector_similarity_search_ranking PASSED      [ 18%]
tests/test_agent_e.py::test_search_with_category_and_price_filters PASSED [ 25%]
tests/test_agent_e.py::test_get_product_details PASSED                   [ 31%]
tests/test_agent_e.py::test_check_inventory_and_low_stock_warning PASSED [ 37%]
tests/test_agent_e.py::test_find_nearby_stores_geospatial PASSED         [ 43%]
tests/test_agent_e.py::test_cart_lifecycle_add_view_remove_clear PASSED  [ 50%]
tests/test_agent_e.py::test_place_order_and_inventory_decrement PASSED   [ 56%]
tests/test_agent_e.py::test_place_order_in_store_pickup PASSED           [ 62%]
tests/test_agent_e.py::test_place_order_empty_cart_fails PASSED          [ 68%]
tests/test_agent_e.py::test_add_to_cart_excess_quantity_fails PASSED     [ 75%]
tests/test_agent_e.py::test_order_status_tracking PASSED                 [ 81%]
tests/test_agent_e.py::test_vector_math_primitives PASSED                [ 87%]
tests/test_agent_e.py::test_fastmcp_tool_registration PASSED             [ 93%]
tests/test_agent_e.py::test_agent_conversational_turn PASSED             [100%]

============================= 16 passed in 5.18s ==============================
```
