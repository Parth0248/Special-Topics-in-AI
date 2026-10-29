"""Shared test fixtures for Google ADK Multi-Agent Suite (e2e adk agents).

Provides zero-flakiness offline mocks for:
1. mock_genai_client: Offline Gemini client mock for text generation and 768-d embeddings.
2. mock_gemini_cli: Subprocess mock for Gemini CLI tool invocation.
3. mock_mcp_client: FastMCP / MCP tool fixture for filesystem and diagnostic tools.
4. test_sports_db: In-memory seeded SQLite catalog for sports agent (Agent E).
"""

import asyncio
import json
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# 1. Environment & Global Test Setup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Sets standard offline test environment variables."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_mock_gemini_api_key_12345")
    monkeypatch.setenv("HARNESS_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-004")
    monkeypatch.setenv("FALLBACK_TO_LOCAL_SQLITE", "true")
    monkeypatch.setenv("AGENT_INTEGRITY_MODE", "demo")
    monkeypatch.delenv("ALLOYDB_HOST", raising=False)


# ---------------------------------------------------------------------------
# 2. Mock GenAI Client (Offline Gemini Mock)
# ---------------------------------------------------------------------------

@dataclass
class MockUsageMetadata:
    prompt_token_count: int = 25
    candidates_token_count: int = 50
    total_token_count: int = 75


@dataclass
class MockPart:
    text: str


@dataclass
class MockContent:
    parts: List[MockPart]
    role: str = "model"


@dataclass
class MockCandidate:
    content: MockContent
    finish_reason: str = "STOP"


class MockGenerateContentResponse:
    def __init__(self, text: str = "Mocked LLM generation output"):
        self._text = text
        self.usage_metadata = MockUsageMetadata()
        self.candidates = [MockCandidate(content=MockContent(parts=[MockPart(text=text)]))]

    @property
    def text(self) -> str:
        return self._text


@dataclass
class MockEmbeddingValue:
    values: List[float]


class MockEmbedContentResponse:
    def __init__(self, embedding_dim: int = 768, seed_val: float = 0.05):
        # Generate normalized unit vector
        vec = np.full(embedding_dim, seed_val, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        self.embeddings = [MockEmbeddingValue(values=vec.tolist())]


class MockChatSession:
    def __init__(self, parent_client):
        self.parent = parent_client
        self.history = []

    def send_message(self, message: str, **kwargs) -> MockGenerateContentResponse:
        self.history.append({"role": "user", "text": message})
        reply_text = f"Mocked chat reply to: {message[:40]}"
        self.history.append({"role": "model", "text": reply_text})
        return MockGenerateContentResponse(text=reply_text)


@pytest.fixture
def mock_genai_client(monkeypatch):
    """Provides a fully mocked Google GenAI Client for text and 768-d embeddings."""
    mock_client = MagicMock()

    # Models mock
    models_mock = MagicMock()

    def generate_content_side_effect(model: str, contents: Any, config: Any = None, **kwargs):
        # Format-aware response
        prompt_str = str(contents)
        if "json" in prompt_str.lower() or (config and getattr(config, "response_mime_type", "") == "application/json"):
            json_text = json.dumps({
                "response": "Automated structured output",
                "status": "success",
                "summary": "Synthesized review / dossier data",
                "score": 88.5
            })
            return MockGenerateContentResponse(text=json_text)
        return MockGenerateContentResponse(text=f"Mocked response for prompt: {prompt_str[:50]}...")

    models_mock.generate_content.side_effect = generate_content_side_effect

    def embed_content_side_effect(model: str, contents: Any, **kwargs):
        return MockEmbedContentResponse(embedding_dim=768)

    models_mock.embed_content.side_effect = embed_content_side_effect
    mock_client.models = models_mock

    # Chats mock
    chats_mock = MagicMock()
    chats_mock.create.return_value = MockChatSession(mock_client)
    mock_client.chats = chats_mock

    # Patch google.genai.Client if importable
    try:
        monkeypatch.setattr("google.genai.Client", lambda *args, **kwargs: mock_client)
    except (ImportError, AttributeError):
        pass

    return mock_client


# ---------------------------------------------------------------------------
# 3. Mock Gemini CLI (Subprocess Mock)
# ---------------------------------------------------------------------------

class MockGeminiCliController:
    """Controls the behavior of the mocked gemini CLI subprocess."""

    def __init__(self):
        self.mode = "success"  # 'success', 'error', 'timeout', 'malformed', 'raw_markdown'
        self.returncode = 0
        self.custom_response = "Generated output from Gemini CLI tool."
        self.custom_stderr = ""
        self.invocation_count = 0
        self.last_command: List[str] = []

    def set_mode(self, mode: str, returncode: int = 0, custom_response: str = "", stderr: str = ""):
        self.mode = mode
        self.returncode = returncode
        if custom_response:
            self.custom_response = custom_response
        if stderr:
            self.custom_stderr = stderr

    def handle_call(self, cmd: List[str], *args, **kwargs):
        self.invocation_count += 1
        self.last_command = cmd

        if self.mode == "timeout":
            timeout_val = kwargs.get("timeout", 10)
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_val)

        if self.mode == "error":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=self.returncode or 1,
                stdout="",
                stderr=self.custom_stderr or "Error: Gemini CLI process failed with code 1"
            )

        if self.mode == "malformed":
            # Embedded JSON in conversational text
            stdout = f"Here is the result:\n```json\n{{\"response\": \"{self.custom_response}\", \"stats\": {{\"tokens\": 24}}}}\n```\nHope that helps!"
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        if self.mode == "raw_markdown":
            stdout = f"## Results\n{self.custom_response}\n- Item 1\n- Item 2"
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        # Default standard JSON success
        stdout_obj = {
            "response": self.custom_response,
            "stats": {"tokens": {"prompt": 15, "candidates": 30}, "latency_ms": 110},
            "error": None
        }
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(stdout_obj),
            stderr=""
        )


@pytest.fixture
def mock_gemini_cli(monkeypatch):
    """Mocks subprocess.run and shutil.which for Gemini CLI invocations."""
    controller = MockGeminiCliController()

    # Ensure shutil.which("gemini") returns a fake binary path by default
    orig_which = shutil_which = os.path.exists
    monkeypatch.setattr("shutil.which", lambda bin_name: "C:\\mock\\bin\\gemini.exe" if "gemini" in bin_name.lower() else None)

    def fake_subprocess_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "gemini" in cmd_str.lower():
            return controller.handle_call(cmd, *args, **kwargs)
        # Pass through other commands or return a clean CompletedProcess
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_output", stderr="")

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)
    return controller


# ---------------------------------------------------------------------------
# 4. Mock MCP Client (FastMCP / Embedded MCP Tool Provider)
# ---------------------------------------------------------------------------

class MockMcpToolProvider:
    """Mock MCP tool provider exposing filesystem, search, git, and execution tools."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.virtual_files: Dict[str, str] = {}
        self.call_log: List[Dict[str, Any]] = []

    def read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        self.call_log.append({"tool": "read_file", "path": path, "start_line": start_line, "end_line": end_line})
        # Check virtual files first
        if path in self.virtual_files:
            content = self.virtual_files[path]
        else:
            # Fall back to real filesystem within tmp_path
            real_path = os.path.join(self.tmp_path, os.path.basename(path))
            if os.path.exists(real_path):
                with open(real_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                raise FileNotFoundError(f"File not found: {path}")

        lines = content.splitlines(keepends=True)
        if start_line is not None or end_line is not None:
            s = (start_line - 1) if (start_line and start_line > 0) else 0
            e = end_line if end_line is not None else len(lines)
            return "".join(lines[s:e])
        return content

    def write_file(self, path: str, content: str) -> str:
        self.call_log.append({"tool": "write_file", "path": path, "bytes": len(content)})
        self.virtual_files[path] = content
        real_path = os.path.join(self.tmp_path, os.path.basename(path))
        with open(real_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"

    def list_directory(self, path: str, recursive: bool = False) -> List[str]:
        self.call_log.append({"tool": "list_directory", "path": path})
        entries = set()
        for f in self.virtual_files.keys():
            entries.add(f)
        for root, dirs, files in os.walk(self.tmp_path):
            for file in files:
                entries.add(file)
        return sorted(list(entries))

    def search_files(self, pattern: str, path: Optional[str] = None, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        self.call_log.append({"tool": "search_files", "pattern": pattern})
        results = []
        regex = re.compile(pattern)
        for fname, content in self.virtual_files.items():
            if extension and not fname.endswith(extension):
                continue
            for idx, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    results.append({"file": fname, "line": idx, "text": line})
        return results

    def run_test_command(self, command: str, cwd: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        self.call_log.append({"tool": "run_test_command", "command": command})
        return {
            "exit_code": 0,
            "stdout": "================ 1 passed in 0.05s ================",
            "stderr": "",
            "duration": 0.05
        }


@pytest.fixture
def mock_mcp_client(tmp_path):
    """Provides an isolated in-memory MCP tool provider."""
    return MockMcpToolProvider(tmp_path=tmp_path)


# ---------------------------------------------------------------------------
# 5. In-Memory Seeded SQLite Catalog for Agent E
# ---------------------------------------------------------------------------

class SportsShopCatalogDB:
    """In-memory SQLite database seeded with sports products, vector embeddings, stores, and inventory."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_data()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        );

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

        CREATE TABLE IF NOT EXISTS inventory (
            inventory_id TEXT PRIMARY KEY,
            product_id TEXT REFERENCES products(product_id),
            store_id TEXT,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            low_stock_threshold INTEGER DEFAULT 5
        );

        CREATE TABLE IF NOT EXISTS carts (
            cart_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cart_items (
            item_id TEXT PRIMARY KEY,
            cart_id TEXT REFERENCES carts(cart_id),
            product_id TEXT REFERENCES products(product_id),
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            fulfillment_type TEXT NOT NULL,
            shipping_address TEXT,
            pickup_store_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id TEXT PRIMARY KEY,
            order_id TEXT REFERENCES orders(order_id),
            product_id TEXT REFERENCES products(product_id),
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
        """)
        self.conn.commit()

    @staticmethod
    def _create_vector(seed_int: int, dim: int = 768) -> bytes:
        """Creates a deterministic unit-normalized 768-d vector."""
        rng = np.random.RandomState(seed_int)
        vec = rng.randn(dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tobytes()

    def _seed_data(self):
        cursor = self.conn.cursor()

        # 1. Categories
        categories = [
            ("CAT-RUN", "Running & Trail", "Trail and road running shoes, spikes, and hydration gear"),
            ("CAT-BSK", "Basketball", "High-performance basketball shoes, apparel, and balls"),
            ("CAT-APP", "Apparel & Outerwear", "Weather-resistant jackets, shorts, and thermal layers"),
            ("CAT-EQP", "Sports Equipment", "Trekking poles, bottles, bags, and training equipment"),
        ]
        cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?, ?)", categories)

        # 2. Products (with deterministic 768-d embeddings)
        products = [
            (
                "PROD-RUN-001", "CAT-RUN", "Apex Trail Pro Shoes", "SummitPeak", 149.99, "USD",
                "Lightweight trail running shoes with aggressive lug traction and rock plate protection.",
                json.dumps(["Vibram Outsole", "Gore-Tex Upper", "Breathable Mesh", "Weight: 290g"]),
                4.8, 142, self._create_vector(101)
            ),
            (
                "PROD-RUN-002", "CAT-RUN", "Velocity Marathon Flats", "AeroStride", 129.99, "USD",
                "Carbon-infused racing flats engineered for maximum energy return on asphalt.",
                json.dumps(["Carbon Fiber Plate", "Ultra-light Foam", "Weight: 195g"]),
                4.6, 89, self._create_vector(102)
            ),
            (
                "PROD-BSK-001", "CAT-BSK", "HyperCourt Elite High-Tops", "SlamDunk", 165.00, "USD",
                "High-top basketball shoes with dual-density air cushioning and lateral ankle support.",
                json.dumps(["Zoom Cushioning", "Herringbone Grip", "Ankle Lockdown"]),
                4.7, 210, self._create_vector(201)
            ),
            (
                "PROD-BSK-002", "CAT-BSK", "StreetGrip Composite Basketball", "SlamDunk", 39.99, "USD",
                "Official size 7 composite leather basketball engineered for indoor and outdoor courts.",
                json.dumps(["Composite Leather", "Deep Channel Design", "Size 7 (29.5 inch)"]),
                4.5, 95, self._create_vector(202)
            ),
            (
                "PROD-APP-001", "CAT-APP", "StormShield Thermal Windbreaker", "AlpineEdge", 89.50, "USD",
                "Ultralight windproof and water-resistant running jacket with packable chest pocket.",
                json.dumps(["DWR Finish", "Reflective Accents", "Packable", "Weight: 120g"]),
                4.7, 64, self._create_vector(301)
            ),
            (
                "PROD-APP-002", "CAT-APP", "ProFlex Compression Tights", "ActiveFlex", 54.00, "USD",
                "Graduated compression running tights with side phone pockets and moisture wicking.",
                json.dumps(["80% Recycled Poly", "20% Spandex", "4-way Stretch"]),
                4.4, 78, self._create_vector(302)
            ),
            (
                "PROD-EQP-001", "CAT-EQP", "CarbonPulse Trekking Poles", "SummitPeak", 79.99, "USD",
                "Collapsible carbon fiber trekking poles with ergonomic cork grips and flick-lock adjusters.",
                json.dumps(["100% Carbon Fiber", "Cork Grip", "Weight: 420g/pair"]),
                4.9, 115, self._create_vector(401)
            ),
            (
                "PROD-EQP-002", "CAT-EQP", "HydraFlow 32oz Insulated Bottle", "HydroActive", 29.99, "USD",
                "Double-wall vacuum insulated stainless steel sports bottle with sport straw lid.",
                json.dumps(["18/8 Stainless Steel", "Keeps cold 24h", "BPA Free"]),
                4.8, 310, self._create_vector(402)
            ),
        ]
        cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", products)

        # 3. Stores
        stores = [
            ("STORE-SJ-001", "San Jose Downtown Sports Hub", "123 S 1st St", "San Jose", "95113", 37.3352, -121.8893, "408-555-0101"),
            ("STORE-SV-002", "Sunnyvale Outdoor World", "456 El Camino Real", "Sunnyvale", "94087", 37.3688, -122.0363, "408-555-0102"),
        ]
        cursor.executemany("INSERT OR IGNORE INTO stores VALUES (?, ?, ?, ?, ?, ?, ?, ?)", stores)

        # 4. Inventory
        inventory_items = []
        inv_id = 1
        for prod in products:
            p_id = prod[0]
            # Central warehouse (store_id is None)
            inventory_items.append((f"INV-{inv_id:04d}", p_id, None, 50, 5))
            inv_id += 1
            # Local store 1
            inventory_items.append((f"INV-{inv_id:04d}", p_id, "STORE-SJ-001", 15, 3))
            inv_id += 1
            # Local store 2
            inventory_items.append((f"INV-{inv_id:04d}", p_id, "STORE-SV-002", 8, 2))
            inv_id += 1

        cursor.executemany("INSERT OR IGNORE INTO inventory VALUES (?, ?, ?, ?, ?)", inventory_items)
        self.conn.commit()

    # -----------------------------------------------------------------------
    # Operational Helpers
    # -----------------------------------------------------------------------

    def search_products(
        self,
        query: str = "",
        query_vector: Optional[np.ndarray] = None,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        sql = "SELECT product_id, category_id, name, brand, price, currency, description, rating, review_count, embedding FROM products WHERE 1=1"
        params = []
        if category:
            sql += " AND (category_id = ? OR category_id LIKE ?)"
            params.extend([category, f"%{category}%"])
        if max_price is not None:
            sql += " AND price <= ?"
            params.append(max_price)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = []

        # If vector is provided, calculate cosine similarity
        if query_vector is not None:
            q_norm = np.linalg.norm(query_vector)
            for r in rows:
                p_vec = np.frombuffer(r["embedding"], dtype=np.float32)
                p_norm = np.linalg.norm(p_vec)
                similarity = float(np.dot(query_vector, p_vec) / (q_norm * p_norm)) if (q_norm > 0 and p_norm > 0) else 0.0
                results.append({
                    "product_id": r["product_id"],
                    "category_id": r["category_id"],
                    "name": r["name"],
                    "brand": r["brand"],
                    "price": r["price"],
                    "currency": r["currency"],
                    "description": r["description"],
                    "rating": r["rating"],
                    "review_count": r["review_count"],
                    "similarity_score": round(similarity, 4)
                })
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
        else:
            # Simple keyword matching fallback
            q_lower = query.lower()
            for r in rows:
                score = 0.5
                if q_lower in r["name"].lower() or q_lower in r["description"].lower() or q_lower in r["brand"].lower():
                    score = 0.95
                results.append({
                    "product_id": r["product_id"],
                    "category_id": r["category_id"],
                    "name": r["name"],
                    "brand": r["brand"],
                    "price": r["price"],
                    "currency": r["currency"],
                    "description": r["description"],
                    "rating": r["rating"],
                    "review_count": r["review_count"],
                    "similarity_score": score
                })
            results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return results[:limit]

    def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        res.pop("embedding", None)
        if isinstance(res.get("features"), str):
            try:
                res["features"] = json.loads(res["features"])
            except Exception:
                pass
        return res

    def check_inventory(self, product_id: str, store_id: Optional[str] = None) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        if store_id:
            cursor.execute("SELECT stock_quantity FROM inventory WHERE product_id = ? AND store_id = ?", (product_id, store_id))
            row = cursor.fetchone()
            qty = row["stock_quantity"] if row else 0
            return {"product_id": product_id, "store_id": store_id, "stock_quantity": qty, "in_stock": qty > 0}
        else:
            cursor.execute("SELECT SUM(stock_quantity) as total FROM inventory WHERE product_id = ?", (product_id,))
            row = cursor.fetchone()
            total = row["total"] if row and row["total"] is not None else 0
            return {"product_id": product_id, "store_id": "ALL", "stock_quantity": total, "in_stock": total > 0}

    def manage_cart(self, action: str, user_id: str, product_id: Optional[str] = None, quantity: int = 1) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        # Ensure cart exists
        cursor.execute("SELECT cart_id FROM carts WHERE user_id = ?", (user_id,))
        cart_row = cursor.fetchone()
        if not cart_row:
            cart_id = f"CART-{user_id}"
            cursor.execute("INSERT INTO carts (cart_id, user_id) VALUES (?, ?)", (cart_id, user_id))
        else:
            cart_id = cart_row["cart_id"]

        if action == "add" and product_id:
            cursor.execute("SELECT price FROM products WHERE product_id = ?", (product_id,))
            prod = cursor.fetchone()
            if not prod:
                return {"error": f"Product {product_id} not found", "success": False}
            unit_price = prod["price"]

            cursor.execute("SELECT item_id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
            existing = cursor.fetchone()
            if existing:
                new_qty = existing["quantity"] + quantity
                cursor.execute("UPDATE cart_items SET quantity = ? WHERE item_id = ?", (new_qty, existing["item_id"]))
            else:
                item_id = f"ITEM-{cart_id}-{product_id}"
                cursor.execute("INSERT INTO cart_items VALUES (?, ?, ?, ?, ?)", (item_id, cart_id, product_id, quantity, unit_price))
            self.conn.commit()

        elif action == "remove" and product_id:
            cursor.execute("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
            self.conn.commit()

        elif action == "clear":
            cursor.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
            self.conn.commit()

        # Fetch current items
        cursor.execute("""
            SELECT ci.product_id, p.name, ci.quantity, ci.unit_price, (ci.quantity * ci.unit_price) as subtotal
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.product_id
            WHERE ci.cart_id = ?
        """, (cart_id,))
        items = [dict(r) for r in cursor.fetchall()]
        total_amount = round(sum(i["subtotal"] for i in items), 2)
        return {
            "success": True,
            "cart_id": cart_id,
            "user_id": user_id,
            "items": items,
            "total_items": sum(i["quantity"] for i in items),
            "total_amount": total_amount
        }

    def place_order(
        self,
        user_id: str,
        shipping_address: Optional[str] = "123 Main St, San Jose, CA",
        fulfillment_type: str = "shipping",
        pickup_store_id: Optional[str] = None
    ) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cart = self.manage_cart("view", user_id)
        if not cart["items"]:
            return {"success": False, "error": "Cannot place order: Cart is empty."}

        order_id = f"ORD-{sqlite3.connect(':memory:').total_changes + 10001}"
        total_amount = cart["total_amount"]

        cursor.execute(
            "INSERT INTO orders (order_id, user_id, total_amount, status, fulfillment_type, shipping_address, pickup_store_id) VALUES (?, ?, ?, 'confirmed', ?, ?, ?)",
            (order_id, user_id, total_amount, fulfillment_type, shipping_address, pickup_store_id)
        )

        for item in cart["items"]:
            order_item_id = f"OI-{order_id}-{item['product_id']}"
            cursor.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                (order_item_id, order_id, item["product_id"], item["quantity"], item["unit_price"])
            )
            # Decrement warehouse stock
            cursor.execute(
                "UPDATE inventory SET stock_quantity = MAX(0, stock_quantity - ?) WHERE product_id = ? AND store_id IS NULL",
                (item["quantity"], item["product_id"])
            )

        # Clear cart
        self.manage_cart("clear", user_id)
        self.conn.commit()

        return {
            "success": True,
            "order_id": order_id,
            "user_id": user_id,
            "status": "confirmed",
            "total_amount": total_amount,
            "fulfillment_type": fulfillment_type,
            "items_count": len(cart["items"])
        }

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        cursor.execute("SELECT product_id, quantity, unit_price FROM order_items WHERE order_id = ?", (order_id,))
        res["items"] = [dict(r) for r in cursor.fetchall()]
        return res


@pytest.fixture
def test_sports_db():
    """Provides a fresh in-memory sports catalog database seeded with 8 products, unit vectors, stores, and inventory."""
    return SportsShopCatalogDB(db_path=":memory:")
