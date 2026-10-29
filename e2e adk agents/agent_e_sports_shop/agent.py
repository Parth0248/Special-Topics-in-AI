"""Agent E: Sports Shop Assistant Persona ('Finn') built for Google ADK.

Supports conversational product discovery, vector similarity search recommendations,
inventory availability checks, cart management, and order checkout.
Operates seamlessly with live Gemini 2.5 Flash function calling or deterministic
offline conversational execution.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional

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

logger = logging.getLogger("agent_e.agent")

FINN_SYSTEM_PROMPT = """You are Finn, an expert and enthusiastic sports gear advisor and shopping assistant.
Your goal is to help athletes and fitness enthusiasts discover the perfect equipment and apparel.

Key Responsibilities:
1. Product Discovery: Use search_products to locate athletic gear using vector similarity search.
2. In-Depth Guidance: Use get_product_details to explain technical materials, specifications, and features.
3. Inventory & Local Fulfillment: Use check_inventory and find_nearby_stores to check stock across retail stores or central warehouse.
4. Cart & Checkout: Use manage_cart and place_order to guide customers smoothly through purchasing.
5. Order Tracking: Use get_order_status to provide delivery updates and tracking IDs.

Tone & Persona:
- Knowledgeable, encouraging, and athletic.
- Proactively highlight key specs (e.g., Gore-Tex, Vibram lugs, carbon fiber plates, merino wool).
- Always confirm inventory before recommending that a customer drive to a store.
"""


class SportsAgent:
    """Conversational sports shopping assistant ('Finn')."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        user_id: str = "customer_guest",
    ) -> None:
        self.name = "finn_sports_assistant"
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.user_id = user_id
        self.conversation_history: List[Dict[str, str]] = []
        self.tools_map: Dict[str, Callable[..., Any]] = {
            "search_products": search_products,
            "get_product_details": get_product_details,
            "check_inventory": check_inventory,
            "find_nearby_stores": find_nearby_stores,
            "manage_cart": manage_cart,
            "place_order": place_order,
            "get_order_status": get_order_status,
        }
        self._genai_client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes Google GenAI client if credentials are provided."""
        if not self.api_key:
            return
        try:
            from google import genai
            self._genai_client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.debug("Could not initialize google.genai: %s", e)
            self._genai_client = None

    def execute_turn(self, user_message: str) -> str:
        """Executes a single conversational turn, calling tools as needed."""
        self.conversation_history.append({"role": "user", "content": user_message})

        # 1. Attempt live Gemini API with function calling if client is active
        if self._genai_client is not None:
            try:
                from google.genai import types

                # Format tools for Gemini API
                tool_declarations = [types.Tool(function_declarations=[
                    types.FunctionDeclaration(
                        name="search_products",
                        description="Searches products in catalog using vector similarity and filters.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "query": types.Schema(type=types.Type.STRING, description="Search query"),
                                "category": types.Schema(type=types.Type.STRING, description="Optional category filter"),
                                "max_price": types.Schema(type=types.Type.NUMBER, description="Optional max price"),
                                "limit": types.Schema(type=types.Type.INTEGER, description="Max results"),
                            },
                            required=["query"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="get_product_details",
                        description="Retrieves full specifications and features for a product SKU.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "product_id": types.Schema(type=types.Type.STRING, description="Product SKU ID"),
                            },
                            required=["product_id"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="check_inventory",
                        description="Checks inventory stock at stores or central warehouse.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "product_id": types.Schema(type=types.Type.STRING, description="Product SKU"),
                                "store_id": types.Schema(type=types.Type.STRING, description="Optional store ID"),
                                "postal_code": types.Schema(type=types.Type.STRING, description="Optional postal code"),
                            },
                            required=["product_id"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="find_nearby_stores",
                        description="Finds nearby retail store locations by postal code or city.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "postal_code": types.Schema(type=types.Type.STRING, description="Zip code"),
                                "city": types.Schema(type=types.Type.STRING, description="City name"),
                            },
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="manage_cart",
                        description="Manages cart: 'view', 'add', 'remove', or 'clear'.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "action": types.Schema(type=types.Type.STRING, description="Action: view, add, remove, clear"),
                                "user_id": types.Schema(type=types.Type.STRING, description="Customer ID"),
                                "product_id": types.Schema(type=types.Type.STRING, description="Product SKU"),
                                "quantity": types.Schema(type=types.Type.INTEGER, description="Quantity"),
                            },
                            required=["action", "user_id"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="place_order",
                        description="Places order and decrements inventory.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "user_id": types.Schema(type=types.Type.STRING, description="Customer ID"),
                                "shipping_address": types.Schema(type=types.Type.STRING, description="Address"),
                                "fulfillment_type": types.Schema(type=types.Type.STRING, description="shipping or in_store_pickup"),
                                "pickup_store_id": types.Schema(type=types.Type.STRING, description="Pickup store ID"),
                            },
                            required=["user_id"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="get_order_status",
                        description="Retrieves status and tracking for an order ID.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "order_id": types.Schema(type=types.Type.STRING, description="Order ID"),
                            },
                            required=["order_id"],
                        ),
                    ),
                ])]

                config = types.GenerateContentConfig(
                    system_instruction=FINN_SYSTEM_PROMPT,
                    tools=tool_declarations,
                    temperature=0.3,
                )

                response = self._genai_client.models.generate_content(
                    model=self.model_name,
                    contents=[msg["content"] for msg in self.conversation_history],
                    config=config,
                )

                # Process potential function calls
                if response.function_calls:
                    for call in response.function_calls:
                        fname = call.name
                        fargs = dict(call.args or {})
                        if fname in self.tools_map:
                            result = self.tools_map[fname](**fargs)
                            return f"[Finn - {fname} executed]\n{json.dumps(result, indent=2)}"

                if response.text:
                    self.conversation_history.append({"role": "assistant", "content": response.text})
                    return response.text
            except Exception as e:
                logger.warning("Gemini API call failed (%s); routing to local assistant reasoning.", e)

        # 2. Deterministic Persona Reasoning Engine (100% offline & reproducible)
        reply = self._reason_offline(user_message)
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    def _reason_offline(self, message: str) -> str:
        """Deterministic reasoning loop executing real catalog tools and formatting Finn's response."""
        m_low = message.lower()

        # Intent: Track / Order Status
        if "order status" in m_low or "track order" in m_low or "where is my order" in m_low:
            ord_match = re.search(r"ord-\d+-\d+", m_low)
            order_id = ord_match.group(0).upper() if ord_match else "ORD-20261029-9999"
            status = get_order_status(order_id)
            if "error" in status:
                return f"Hey there! I checked for order **{order_id}**, but couldn't locate it in the system. Could you double-check your order number?"
            return (
                f"Great news! Here is the update on order **{status['order_id']}**:\n"
                f"- **Status**: {status['status'].upper()}\n"
                f"- **Fulfillment**: {status['fulfillment_type']}\n"
                f"- **Total Amount**: ${status['total_amount']:.2f}\n"
                f"- **Items**: {len(status['items'])} item(s) confirmed\n"
                f"We're packing and prepping it for swift delivery!"
            )

        # Intent: Checkout / Place Order
        if "place order" in m_low or "checkout" in m_low or "buy now" in m_low:
            order = place_order(user_id=self.user_id, fulfillment_type="shipping", shipping_address="1 Washington Sq, San Jose, CA 95192")
            if "error" in order:
                return f"Hold on a second! {order['error']} Feel free to ask me to show our top gear so we can add something awesome to your cart first!"
            return (
                f"Boom! Your order has been placed successfully! 🎉\n\n"
                f"- **Order ID**: `{order['order_id']}`\n"
                f"- **Total Paid**: ${order['total_amount']:.2f} (Tax: ${order['tax']:.2f}, Shipping: ${order['shipping']:.2f})\n"
                f"- **Tracking Number**: `{order['tracking_number']}`\n"
                f"- **Estimated Delivery**: {order['estimated_delivery']}\n"
                f"Your items have been reserved and inventory deducted. Thanks for shopping with Finn!"
            )

        # Intent: View Cart
        if "view cart" in m_low or "show cart" in m_low or "what's in my cart" in m_low or "my cart" in m_low:
            cart = manage_cart(action="view", user_id=self.user_id)
            items = cart.get("items", [])
            if not items:
                return "Your sports cart is currently empty! Let me know what sport you're gearing up for and I'll find you top-rated recommendations."

            lines = ["Here is what you've got in your cart so far:"]
            for it in items:
                lines.append(f"• **{it['name']}** x{it['quantity']} @ ${it['unit_price']:.2f} = ${it['line_total']:.2f}")
            lines.append(f"\n**Subtotal**: ${cart['subtotal']:.2f}")
            lines.append(f"**Tax (8.5%)**: ${cart['tax']:.2f}")
            shipping_str = "FREE" if cart["shipping"] == 0 else f"${cart['shipping']:.2f}"
            lines.append(f"**Shipping**: {shipping_str}")
            lines.append(f"**Grand Total**: ${cart['total_amount']:.2f}")
            if not cart["free_shipping_eligible"]:
                diff = 75.0 - cart["subtotal"]
                lines.append(f"*(Add ${diff:.2f} more to qualify for FREE shipping!)*")
            lines.append("\nReady to checkout? Just say **'checkout'** or **'place order'**!")
            return "\n".join(lines)

        # Intent: Add to Cart
        if "add to cart" in m_low or "add" in m_low and ("shoe" in m_low or "jacket" in m_low or "ball" in m_low or "prod-" in m_low):
            pid_match = re.search(r"prod-[a-z]+-\d+", m_low)
            if pid_match:
                prod_id = pid_match.group(0).upper()
            else:
                # Default search for the item mentioned
                found = search_products(query=message, limit=1)
                prod_id = found[0]["product_id"] if found else "PROD-RUN-001"

            cart = manage_cart(action="add", user_id=self.user_id, product_id=prod_id, quantity=1)
            if "error" in cart:
                return f"Sorry about that! {cart['error']}"

            details = get_product_details(prod_id)
            p_name = details.get("name", prod_id)
            free_ship_str = "Unlocked! 🚀" if cart["free_shipping_eligible"] else f"${(75.0 - cart['subtotal']):.2f} away"
            return (
                f"Awesome choice! I've added **{p_name}** to your cart. 🛒\n"
                f"- **Current Cart Total**: ${cart['total_amount']:.2f} ({cart['item_count']} item(s))\n"
                f"- Free Shipping: {free_ship_str}\n\n"
                f"Would you like to keep shopping or proceed to **checkout**?"
            )

        # Intent: Inventory Check
        if "inventory" in m_low or "stock" in m_low or "in stock" in m_low:
            pid_match = re.search(r"prod-[a-z]+-\d+", m_low)
            prod_id = pid_match.group(0).upper() if pid_match else "PROD-RUN-001"
            store_id = "STORE-SJ-001" if ("san jose" in m_low or "sj" in m_low) else None
            inv = check_inventory(product_id=prod_id, store_id=store_id, postal_code="95113")

            if "error" in inv:
                return f"I couldn't verify inventory: {inv['error']}"

            store_str = f"at **{inv.get('store_name') or 'local store'}**: {inv.get('store_stock', 0)} in stock" if inv.get("store_stock") is not None else ""
            return (
                f"Inventory update for **{inv['product_name']}** (`{inv['product_id']}`):\n"
                f"- **Central Warehouse**: {inv['warehouse_stock']} units available\n"
                f"- **Total Network Stock**: {inv['total_network_stock']} units\n"
                f"{store_str}\n"
                f"- Status: {'In Stock & Ready to Ship! ✅' if inv['in_stock'] else 'Sold Out ⚠️'}"
            )

        # Intent: Nearby Stores
        if "store" in m_low or "near me" in m_low or "location" in m_low:
            city = "San Jose" if "san jose" in m_low else ("San Francisco" if "san francisco" in m_low else None)
            stores = find_nearby_stores(postal_code="95113", city=city)
            lines = ["Here are our nearest retail locations:"]
            for s in stores[:3]:
                dist_str = f"({s['distance_miles']} miles away)" if "distance_miles" in s else ""
                lines.append(f"• **{s['name']}** {dist_str}\n  {s['address']}, {s['city']}, CA {s['postal_code']} | 📞 {s['phone']}")
            lines.append("\nYou can select in-store pickup during checkout!")
            return "\n".join(lines)

        # Default Intent: Vector Product Search
        price_match = re.search(r"under\s+\$?(\d+)", m_low)
        max_p = float(price_match.group(1)) if price_match else None

        category = None
        for cat in ("running", "basketball", "outdoor", "equipment"):
            if cat in m_low:
                category = cat
                break

        results = search_products(query=message, category=category, max_price=max_p, limit=3)
        if not results:
            return (
                "Hey! I searched our sports catalog, but couldn't find a direct match. "
                "We carry top gear across running shoes, basketball, outdoor hiking apparel, and fitness equipment. "
                "What type of sport or activity are you looking to equip for?"
            )

        lines = ["Hey! Finn here. Based on our vector similarity search, here are top picks tailored for you:"]
        for p in results:
            lines.append(
                f"\n🏅 **{p['name']}** — **${p['price']:.2f}** (Score: {p['similarity_score']:.2f} | Rating: {p['rating']}★ / {p['review_count']} reviews)\n"
                f"   *SKU: `{p['product_id']}` | Brand: {p['brand']}*\n"
                f"   {p['description']}\n"
                f"   **Features**: {p['features']}"
            )
        lines.append(
            "\nLet me know if you'd like me to **check local store stock** or **add an item to your cart**!"
        )
        return "\n".join(lines)


def create_sports_agent(
    model_name: str = "gemini-2.5-flash",
    api_key: Optional[str] = None,
    user_id: str = "customer_guest",
) -> SportsAgent:
    """Factory creating an instance of Finn the Sports Shopping Assistant."""
    return SportsAgent(model_name=model_name, api_key=api_key, user_id=user_id)
