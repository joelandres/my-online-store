from langchain_core.tools import tool

@tool("calculate_product_price")
def calculate_product_price(item_name: str, apply_discount: bool = False) -> str:
    """Calculates the total cost of a product including a 7% sales tax and optional 10% discount."""
    prices = {"coffee mug": 15.00, "laptop stand": 45.00}
    item_lower = item_name.lower()
    
    if item_lower not in prices:
        return f"Could not generate a quote. '{item_name}' pricing data is missing."
        
    price = prices[item_lower]
    if apply_discount:
        price *= 0.90
    
    final_total = price * 1.07
    return f"The final price for '{item_name}' (including 7% tax) is ${final_total:.2f}."