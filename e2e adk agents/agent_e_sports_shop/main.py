"""CLI entry point for Agent E: Sports Shop Agent ('Finn').

Supports:
- Interactive conversational mode: --interactive
- Single-query execution: --query "Find trail running shoes under $160"
- Automated end-to-end demo: --demo
"""

from __future__ import annotations

import argparse
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from .agent import create_sports_agent
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
    from agent import create_sports_agent
    from tools import (
        check_inventory,
        find_nearby_stores,
        get_order_status,
        get_product_details,
        manage_cart,
        place_order,
        search_products,
    )

console = Console()


def print_banner() -> None:
    """Displays the Agent E startup banner."""
    console.print(
        Panel.fit(
            "[bold cyan]Agent E: E-Commerce Sports Shop Assistant ('Finn')[/bold cyan]\n"
            "[italic green]Powered by Google ADK & Dual-Mode AlloyDB + Local SQLite Vector Store[/italic green]\n"
            "[yellow]Features: 768-d Vector Cosine Search | FastMCP Tools | Inventory & Cart Management[/yellow]",
            border_style="cyan",
        )
    )


def run_interactive(user_id: str = "interactive_shopper") -> None:
    """Runs a multi-turn interactive shopping session with Finn."""
    print_banner()
    agent = create_sports_agent(user_id=user_id)
    console.print(
        "[bold green]Finn is online![/bold green] Ask anything about athletic gear, running shoes, "
        "basketball equipment, store inventory, or checkout. Type [bold red]'exit'[/bold red] or [bold red]'quit'[/bold red] to end.\n"
    )

    while True:
        try:
            user_input = console.input("[bold yellow]You > [/bold yellow]").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n[bold cyan]Finn:[/bold cyan] Thanks for stopping by! Keep pushing your limits! 🏃‍♂️💨")
                break

            response = agent.execute_turn(user_input)
            console.print(f"\n[bold cyan]Finn:[/bold cyan]\n{response}\n")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Finn:[/bold cyan] Session closed. Have a great workout!")
            break


def run_query(query: str, user_id: str = "query_shopper") -> None:
    """Executes a single prompt through Finn and prints the response."""
    print_banner()
    agent = create_sports_agent(user_id=user_id)
    console.print(f"[bold yellow]Query:[/bold yellow] {query}\n")
    response = agent.execute_turn(query)
    console.print(f"[bold cyan]Finn:[/bold cyan]\n{response}\n")


def run_demo(user_id: str = "demo_athlete_01") -> None:
    """Runs an automated, end-to-end shopping demo exhibiting all 7 FastMCP tools."""
    print_banner()
    console.print("\n[bold magenta]=== Starting Agent E Automated Shopping Demonstration ===[/bold magenta]\n")

    time.sleep(0.5)

    # Step 1: Vector Similarity Search
    console.print("[bold yellow][Step 1/8] Vector Similarity Search for Trail Running Shoes[/bold yellow]")
    query = "breathable waterproof mountain trail running shoes with rock protection"
    console.print(f"Search Query: [italic]'{query}'[/italic]")
    results = search_products(query=query, category="running", max_price=160.0, limit=2)

    table = Table(title="Vector Search Results (Top Matches)")
    table.add_column("SKU", style="cyan")
    table.add_column("Product Name", style="bold white")
    table.add_column("Price", style="green")
    table.add_column("Score", style="yellow")
    table.add_column("Rating", style="magenta")

    for r in results:
        table.add_row(
            r["product_id"],
            r["name"],
            f"${r['price']:.2f}",
            f"{r['similarity_score']:.4f}",
            f"{r['rating']}★ ({r['review_count']})",
        )
    console.print(table)
    selected_product_id = results[0]["product_id"] if results else "PROD-RUN-001"

    # Step 2: Get Product Details
    console.print(f"\n[bold yellow][Step 2/8] Retrieving Detailed Specifications for SKU: {selected_product_id}[/bold yellow]")
    details = get_product_details(selected_product_id)
    console.print(
        Panel(
            f"[bold]{details['name']}[/bold] ({details['brand']})\n"
            f"[dim]{details['description']}[/dim]\n\n"
            f"[bold cyan]Technical Features:[/bold cyan] {details['features']}\n"
            f"[bold green]Price:[/bold green] ${details['price']:.2f} {details['currency']} | [bold magenta]Rating:[/bold magenta] {details['rating']}★\n"
            f"[bold yellow]Network Inventory:[/bold yellow] {details['total_available_stock']} units available",
            title="Product Dossier",
            border_style="green",
        )
    )

    # Step 3: Check Inventory Availability
    console.print("\n[bold yellow][Step 3/8] Checking Multi-Tier Inventory & Stock Thresholds[/bold yellow]")
    inv_check = check_inventory(product_id=selected_product_id, postal_code="95113")
    console.print(
        f"• Central Warehouse: [bold cyan]{inv_check['warehouse_stock']}[/bold cyan] units\n"
        f"• Local Store ({inv_check.get('store_name', 'San Jose Hub')}): [bold cyan]{inv_check.get('store_stock', 'N/A')}[/bold cyan] units\n"
        f"• Total Network Availability: [bold green]{inv_check['total_network_stock']}[/bold green] units\n"
        f"• Low Stock Warning: {'[bold red]YES[/bold red]' if inv_check['low_stock_warning'] else '[bold green]NO (Healthy Stock)[/bold green]'}"
    )

    # Step 4: Find Nearby Retail Stores
    console.print("\n[bold yellow][Step 4/8] Finding Nearby Retail Stores for Local Pickup[/bold yellow]")
    stores = find_nearby_stores(postal_code="95113")
    store_table = Table(title="Nearby Sports Retail Hubs")
    store_table.add_column("Store ID", style="cyan")
    store_table.add_column("Store Name", style="white")
    store_table.add_column("City", style="green")
    store_table.add_column("Distance", style="yellow")
    store_table.add_column("Phone", style="dim")

    for s in stores[:3]:
        dist = f"{s.get('distance_miles', 'N/A')} mi"
        store_table.add_row(s["store_id"], s["name"], s["city"], dist, s["phone"])
    console.print(store_table)

    # Step 5: Manage Cart - Add Items
    console.print("\n[bold yellow][Step 5/8] Managing Shopping Cart (Adding Product)[/bold yellow]")
    manage_cart(action="add", user_id=user_id, product_id=selected_product_id, quantity=1)
    console.print(f"Added [bold]{selected_product_id}[/bold] to cart. Status: [bold green]Success[/bold green]")

    # Step 6: View Cart
    console.print("\n[bold yellow][Step 6/8] Viewing Active Cart & Calculating Taxes/Shipping[/bold yellow]")
    cart = manage_cart(action="view", user_id=user_id)
    cart_table = Table(title=f"Active Cart: {cart['cart_id']}")
    cart_table.add_column("Item", style="white")
    cart_table.add_column("Qty", style="cyan")
    cart_table.add_column("Unit Price", style="green")
    cart_table.add_column("Line Total", style="bold green")

    for item in cart["items"]:
        cart_table.add_row(item["name"], str(item["quantity"]), f"${item['unit_price']:.2f}", f"${item['line_total']:.2f}")
    console.print(cart_table)
    shipping_disp = "FREE" if cart["shipping"] == 0 else f"${cart['shipping']:.2f}"
    console.print(
        f"Subtotal: ${cart['subtotal']:.2f} | Tax (8.5%): ${cart['tax']:.2f} | "
        f"Shipping: {shipping_disp} | "
        f"[bold cyan]Grand Total: ${cart['total_amount']:.2f}[/bold cyan]"
    )

    # Step 7: Place Order & Decrement Inventory
    console.print("\n[bold yellow][Step 7/8] Placing Confirmed Order & Decrementing Inventory[/bold yellow]")
    initial_stock = inv_check["warehouse_stock"]
    order = place_order(
        user_id=user_id,
        shipping_address="1 Washington Sq, San Jose, CA 95192",
        fulfillment_type="shipping",
    )
    console.print(
        Panel(
            f"[bold green]Order Placed Successfully![/bold green]\n"
            f"[bold]Order ID:[/bold] `{order['order_id']}`\n"
            f"[bold]Tracking Number:[/bold] `{order['tracking_number']}`\n"
            f"[bold]Total Paid:[/bold] ${order['total_amount']:.2f}\n"
            f"[bold]Estimated Delivery:[/bold] {order['estimated_delivery']}\n"
            f"[bold]Destination:[/bold] {order['shipping_address']}",
            title="Order Receipt",
            border_style="cyan",
        )
    )

    # Step 8: Order Status Tracking & Verification
    console.print("\n[bold yellow][Step 8/8] Verifying Tracking & Inventory Decrement[/bold yellow]")
    status = get_order_status(order["order_id"])
    console.print(f"• Verified Order ID `{status['order_id']}`: Status = [bold green]{status['status'].upper()}[/bold green]")

    new_inv = check_inventory(product_id=selected_product_id)
    new_stock = new_inv["warehouse_stock"]
    console.print(f"• Central Warehouse Stock Before: [bold yellow]{initial_stock}[/bold yellow] -> After: [bold green]{new_stock}[/bold green] (Decremented by 1 unit)")
    assert new_stock == initial_stock - 1, "Inventory was not decremented correctly!"

    # Verify Cart is now cleared
    cart_after = manage_cart(action="view", user_id=user_id)
    assert len(cart_after["items"]) == 0, "Cart was not emptied after order placement!"
    console.print("• Active Cart Status: [bold green]Cleared (0 items remaining)[/bold green]")

    console.print(
        Panel.fit(
            "[bold green]✔ Demonstration Complete: All 7 FastMCP tools executed with 100% data integrity![/bold green]",
            border_style="green",
        )
    )


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Agent E: Sports Shop Agent with AlloyDB + Local SQLite Vector Fallback"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start multi-turn interactive shopping chat with Finn",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Run a single conversational prompt through Finn",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run an automated end-to-end shopping workflow demo",
    )

    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.query:
        run_query(args.query)
    elif args.demo:
        run_demo()
    else:
        # Default to demo mode if no arguments provided
        run_demo()


if __name__ == "__main__":
    main()
