import random
import json
import re
from langchain_core.tools import tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

# 3. Production Tools w/ validation
@tool
def product_search(query: str, category: str | None = None) -> str:
    """Search catalog. Returns JSON."""
    # Prod: Elasticsearch + caching
    products = [
        {"id": "laptop123", "name": "ProBook", "price": 999, "stock": random.randint(0, 50)},
        {"id": "laptop456", "name": "Gaming Beast", "price": 1499, "stock": random.randint(0, 50)},
        {"id": "laptop789", "name": "UltraLight", "price": 1199, "stock": random.randint(0, 50)}
    ]
    # Return a random subset or different stock levels each time
    selected_products = random.sample(products, k=random.randint(1, len(products)))
    return json.dumps(selected_products)

@tool
def get_inventory(sku: str) -> str:
    """Check stock levels."""
    if not re.match(r'^[a-zA-Z0-9]{8,12}$', sku):
        raise ValueError("Invalid SKU format")
    # Prod: Redis query
    stock = random.randint(0, 100)
    return f'{sku}: {"✅ " + str(stock) + " in stock" if stock > 0 else "❌ Out of stock"}'

@tool
def duckduckgo_search(query: str) -> str:
    """Search DuckDuckGo for information based on the query."""
    search = DuckDuckGoSearchAPIWrapper()
    return search.run(query)

tools = [product_search, get_inventory, duckduckgo_search]
