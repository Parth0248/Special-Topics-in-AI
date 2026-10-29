"""Seed data catalog for Agent E: Sports Shop Agent.

Provides categories, rich synthetic sports products across running shoes,
basketball gear, outdoor apparel, and equipment, physical retail stores,
and multi-tier inventory distribution (central warehouse and retail locations).
"""

from __future__ import annotations

from typing import Any, Dict, List

CATEGORIES: List[Dict[str, Any]] = [
    {
        "category_id": "running",
        "name": "Running Shoes & Gear",
        "description": "Trail running shoes, marathon road shoes, performance singlets, and hydration packs.",
    },
    {
        "category_id": "basketball",
        "name": "Basketball Gear & Apparel",
        "description": "High-top basketball sneakers, composite leather balls, performance shorts, and knee pads.",
    },
    {
        "category_id": "outdoor",
        "name": "Outdoor Apparel & Hiking",
        "description": "Waterproof storm jackets, carbon trekking poles, merino wool baselayers, and expedition packs.",
    },
    {
        "category_id": "equipment",
        "name": "Fitness Equipment & Recovery",
        "description": "Hex rubber dumbbells, high-density foam rollers, speed jump ropes, and resistance band sets.",
    },
]

PRODUCTS: List[Dict[str, Any]] = [
    # --- Running (4 items) ---
    {
        "product_id": "PROD-RUN-001",
        "category_id": "running",
        "name": "Apex Trailblazer GTX Trail Running Shoes",
        "brand": "Apex Performance",
        "price": 149.99,
        "currency": "USD",
        "description": "Rugged waterproof trail running shoes engineered for mountain terrain. Features Gore-Tex membrane, Vibram Megagrip lugged outsole, and responsive rock protection plate.",
        "features": "Gore-Tex waterproof membrane; Vibram Megagrip 5mm lugs; Ortholite anti-microbial insole; 290g per shoe; 8mm heel drop",
        "rating": 4.8,
        "review_count": 128,
    },
    {
        "product_id": "PROD-RUN-002",
        "category_id": "running",
        "name": "CloudStrata Road Elite Carbon Marathon Shoes",
        "brand": "CloudStrata",
        "price": 189.99,
        "currency": "USD",
        "description": "Ultra-lightweight marathon road racing shoe featuring full-length carbon fiber propulsion plate and dual-density supercritical foam for maximum energy return.",
        "features": "Full carbon fiber plate; Supercritical PEBA foam; Engineered jacquard mesh upper; 195g per shoe; 6mm heel drop",
        "rating": 4.9,
        "review_count": 94,
    },
    {
        "product_id": "PROD-RUN-003",
        "category_id": "running",
        "name": "Velocity Pace Breathable Singlet",
        "brand": "Apex Performance",
        "price": 39.99,
        "currency": "USD",
        "description": "Featherlight racing singlet with zoned laser-cut ventilation and rapid-dry moisture management fabric. Prevents chafing during ultra-distance runs.",
        "features": "Bonded seam construction; 100% recycled polyester; 360-degree reflective accents; UPF 30+ sun protection",
        "rating": 4.6,
        "review_count": 45,
    },
    {
        "product_id": "PROD-RUN-004",
        "category_id": "running",
        "name": "Endurance 5L Trail Running Hydration Vest",
        "brand": "TerraEquip",
        "price": 89.99,
        "currency": "USD",
        "description": "Ergonomic 5-liter hydration vest including dual 500ml HydraPak soft flasks with bite valves. Form-fitting bounce-free harness with front phone pocket.",
        "features": "Includes 2x 500ml soft flasks; 3D air-mesh breathable back panel; Trekking pole attachment loops; Emergency whistle included",
        "rating": 4.7,
        "review_count": 82,
    },
    # --- Basketball (4 items) ---
    {
        "product_id": "PROD-BSK-001",
        "category_id": "basketball",
        "name": "HyperCourt Pro High-Top Basketball Shoes",
        "brand": "HyperCourt",
        "price": 159.99,
        "currency": "USD",
        "description": "Elite high-top basketball shoes designed for explosive vertical play and lateral stability. Molded external heel counter and dual Zoom Air cushioning units.",
        "features": "Dual Zoom Air units; High-top collar with Achilles padding; Multidirectional herringbone rubber traction; TPU lateral shank",
        "rating": 4.7,
        "review_count": 115,
    },
    {
        "product_id": "PROD-BSK-002",
        "category_id": "basketball",
        "name": "Legacy Precision Indoor/Outdoor Composite Basketball",
        "brand": "Legacy Athletics",
        "price": 49.99,
        "currency": "USD",
        "description": "Official regulation Size 7 basketball with moisture-absorbing microfiber composite cover. Deep channel grooves provide superior fingertip control.",
        "features": "Official Size 7 (29.5 inches); Microfiber composite leather; Cushion core carcass; Rotationally balanced butyl bladder",
        "rating": 4.8,
        "review_count": 210,
    },
    {
        "product_id": "PROD-BSK-003",
        "category_id": "basketball",
        "name": "Slam Dunk Performance 7-Inch Mesh Shorts",
        "brand": "HyperCourt",
        "price": 44.99,
        "currency": "USD",
        "description": "Breathable double-layer mesh basketball shorts with modern 7-inch inseam. Deep zippered media pockets keep essentials secure during pickup games.",
        "features": "7-inch inseam; Heavyweight open-hole mesh with smooth lining; Deep zippered pockets; Striped ribbed waistband with braided drawcord",
        "rating": 4.5,
        "review_count": 67,
    },
    {
        "product_id": "PROD-BSK-004",
        "category_id": "basketball",
        "name": "ProImpact Hex Protective Knee Sleeves (Pair)",
        "brand": "Legacy Athletics",
        "price": 34.99,
        "currency": "USD",
        "description": "Engineered compression knee sleeves with 9mm closed-cell Hex foam padding protecting the patella against hard court floor impacts.",
        "features": "Pair of 2 sleeves; 9mm anatomical Hex technology padding; Moisture management compression fabric; Non-slip silicone upper band",
        "rating": 4.7,
        "review_count": 88,
    },
    # --- Outdoor (4 items) ---
    {
        "product_id": "PROD-OUT-001",
        "category_id": "outdoor",
        "name": "Alpine StormShield 3-Layer Waterproof Rain Jacket",
        "brand": "SummitPeak",
        "price": 199.99,
        "currency": "USD",
        "description": "Technical 3-layer waterproof mountaineering jacket with 28,000mm hydrostatic head rating. Fully seam-taped with waterproof YKK AquaGuard pit zips.",
        "features": "3-layer Gore-Tex Pro shell; 28,000mm waterproof / 20,000g breathability; Two-way underarm pit zips; Helmet-compatible hood with storm brim",
        "rating": 4.9,
        "review_count": 142,
    },
    {
        "product_id": "PROD-OUT-002",
        "category_id": "outdoor",
        "name": "TerraTrek Carbon Fiber Ultralight Trekking Poles",
        "brand": "TerraEquip",
        "price": 79.99,
        "currency": "USD",
        "description": "Collapsible 3-section 100% carbon fiber trekking poles with moisture-wicking natural cork grips and aluminum quick-flick lever locks.",
        "features": "100% carbon fiber shafts; Pair weight only 390g; Natural cork handles with EVA foam grip extensions; Includes carbide tips, rubber feet, mud/snow baskets",
        "rating": 4.8,
        "review_count": 97,
    },
    {
        "product_id": "PROD-OUT-003",
        "category_id": "outdoor",
        "name": "Summit 260 Thermal Merino Wool Baselayer Crew",
        "brand": "SummitPeak",
        "price": 84.99,
        "currency": "USD",
        "description": "Heavyweight 260gsm 100% pure New Zealand merino wool thermal crewneck. Naturally odor-resistant, breathable, and insulates even when damp.",
        "features": "260gsm pure New Zealand merino wool; Flatlock non-chafing seams; Drop-tail hem for full coverage; Natural antimicrobial odor resistance",
        "rating": 4.8,
        "review_count": 76,
    },
    {
        "product_id": "PROD-OUT-004",
        "category_id": "outdoor",
        "name": "Nomad 45L Technical Expedition Backpack",
        "brand": "TerraEquip",
        "price": 169.99,
        "currency": "USD",
        "description": "Versatile 45-liter weekend backpacking pack with internal aluminum stay suspension, floating top lid, sleeping bag compartment, and rain cover.",
        "features": "45L volume + 5L expandable collar; Lightweight 6061-T6 aluminum frame; Integrated removable neon rain cover; Hydration bladder sleeve & port",
        "rating": 4.7,
        "review_count": 63,
    },
    # --- Equipment (4 items) ---
    {
        "product_id": "PROD-EQP-001",
        "category_id": "equipment",
        "name": "ProGrip 50lb Rubber Encased Hex Dumbbell Set",
        "brand": "IronCore Fitness",
        "price": 129.99,
        "currency": "USD",
        "description": "Premium pair of 25lb hex dumbbells (50lb total set). Heavy-duty rubber-encased heads prevent floor damage and rolling; ergonomically contoured knurled chrome handles.",
        "features": "Pair of 25lb dumbbells; Anti-roll hexagonal shape; Commercial grade vulcanized rubber coating; Ergonomic knurled chrome grip handles",
        "rating": 4.9,
        "review_count": 184,
    },
    {
        "product_id": "PROD-EQP-002",
        "category_id": "equipment",
        "name": "UltraRecovery 36-Inch High-Density Foam Roller",
        "brand": "IronCore Fitness",
        "price": 29.99,
        "currency": "USD",
        "description": "Full-length 36-inch high-density molded EVA foam roller for myofascial release, deep tissue recovery, core stability, and post-workout muscle relief.",
        "features": "Full 36-inch length x 6-inch diameter; Molded high-density closed-cell EVA foam; Does not lose shape under heavy repeated compression; Wipe-clean surface",
        "rating": 4.7,
        "review_count": 156,
    },
    {
        "product_id": "PROD-EQP-003",
        "category_id": "equipment",
        "name": "SpeedWire Pro Ball-Bearing Speed Jump Rope",
        "brand": "IronCore Fitness",
        "price": 24.99,
        "currency": "USD",
        "description": "High-velocity speed jump rope with 360-degree precision dual ball bearings. Polymer-coated steel cable designed for effortless double-unders.",
        "features": "Dual 360-degree ball bearings; 10-foot adjustable kink-free vinyl coated steel cable; Non-slip knurled aluminum alloy handles; Includes spare cable",
        "rating": 4.6,
        "review_count": 92,
    },
    {
        "product_id": "PROD-EQP-004",
        "category_id": "equipment",
        "name": "PowerFlex Stackable Resistance Bands Set (150lbs)",
        "brand": "IronCore Fitness",
        "price": 39.99,
        "currency": "USD",
        "description": "Comprehensive 11-piece resistance band system with 5 color-coded natural latex tubes providing up to 150 lbs of stackable resistance.",
        "features": "5 tube bands (10lb to 50lb, stackable to 150lb); 2 cushioned soft-grip handles; 2 padded ankle straps; Heavy-duty door anchor; Waterproof carry bag",
        "rating": 4.8,
        "review_count": 140,
    },
]

STORES: List[Dict[str, Any]] = [
    {
        "store_id": "STORE-SJ-001",
        "name": "Downtown San Jose Athletics Hub",
        "address": "150 S First St",
        "city": "San Jose",
        "postal_code": "95113",
        "latitude": 37.3344,
        "longitude": -121.8893,
        "phone": "(408) 555-0101",
    },
    {
        "store_id": "STORE-SF-002",
        "name": "Union Square Sports Pavilion",
        "address": "850 Market St",
        "city": "San Francisco",
        "postal_code": "94102",
        "latitude": 37.7845,
        "longitude": -122.4070,
        "phone": "(415) 555-0144",
    },
    {
        "store_id": "STORE-PA-003",
        "name": "Stanford Mall Sports & Outdoor",
        "address": "660 Stanford Shopping Center",
        "city": "Palo Alto",
        "postal_code": "94304",
        "latitude": 37.4435,
        "longitude": -122.1712,
        "phone": "(650) 555-0188",
    },
    {
        "store_id": "STORE-OAK-004",
        "name": "East Bay Athletics & Mountain Gear",
        "address": "3400 Broadway",
        "city": "Oakland",
        "postal_code": "94611",
        "latitude": 37.8205,
        "longitude": -122.2589,
        "phone": "(510) 555-0122",
    },
]

# Generate multi-tier inventory: Central warehouse + physical stores
INVENTORY_SEED: List[Dict[str, Any]] = []

for prod in PRODUCTS:
    pid = prod["product_id"]
    # 1. Central warehouse stock (healthy inventory)
    INVENTORY_SEED.append({
        "inventory_id": f"INV-WH-{pid}",
        "product_id": pid,
        "store_id": "WAREHOUSE-CENTRAL",
        "stock_quantity": 45,
        "low_stock_threshold": 5,
    })
    # 2. San Jose Store (flagship store, high stock)
    INVENTORY_SEED.append({
        "inventory_id": f"INV-SJ-{pid}",
        "product_id": pid,
        "store_id": "STORE-SJ-001",
        "stock_quantity": 12,
        "low_stock_threshold": 4,
    })
    # 3. SF Store
    INVENTORY_SEED.append({
        "inventory_id": f"INV-SF-{pid}",
        "product_id": pid,
        "store_id": "STORE-SF-002",
        "stock_quantity": 8,
        "low_stock_threshold": 3,
    })
    # 4. Palo Alto Store (intentional low stock on high-demand items for testing)
    stock_pa = 2 if pid in ("PROD-RUN-001", "PROD-OUT-001") else 6
    INVENTORY_SEED.append({
        "inventory_id": f"INV-PA-{pid}",
        "product_id": pid,
        "store_id": "STORE-PA-003",
        "stock_quantity": stock_pa,
        "low_stock_threshold": 3,
    })
    # 5. Oakland Store (out of stock on PROD-RUN-002 for edge case testing)
    stock_oak = 0 if pid == "PROD-RUN-002" else 5
    INVENTORY_SEED.append({
        "inventory_id": f"INV-OAK-{pid}",
        "product_id": pid,
        "store_id": "STORE-OAK-004",
        "stock_quantity": stock_oak,
        "low_stock_threshold": 2,
    })
