import logging
import os

import requests
from flask import Flask, jsonify, render_template, request
from opentelemetry import baggage, context, trace

shop = Flask(__name__, template_folder=".")
inventory_app = Flask("inventory")
shop.logger.setLevel(logging.INFO)
inventory_app.logger.setLevel(logging.INFO)

PRODUCTS = {
    1: {"name": "Canvas tote", "price_cents": 1800, "stock": 12},
    2: {"name": "Ceramic mug", "price_cents": 1400, "stock": 8},
    3: {"name": "Pocket notebook", "price_cents": 900, "stock": 20},
}


def demo_cohort():
    # Keep the demonstration attribute bounded and avoid logging arbitrary baggage.
    value = baggage.get_baggage("demo.cohort")
    if value in ("web", "demo"):
        trace.get_current_span().set_attribute("shop.demo.cohort", value)
        return value
    return None


tracer = trace.get_tracer(__name__)
ENDPOINT_BAGGAGE = "shop.endpoint"
INVENTORY_CALLERS = {"checkout", "product_stock"}


def check_inventory(product_id, simulate_error=False):
    endpoint = request.endpoint
    trace.get_current_span().set_attribute(ENDPOINT_BAGGAGE, endpoint)
    token = context.attach(baggage.set_baggage(ENDPOINT_BAGGAGE, endpoint))
    try:
        with tracer.start_as_current_span("shop.check_inventory") as span:
            span.set_attribute("shop.product_id", product_id)
            span.set_attribute(ENDPOINT_BAGGAGE, endpoint)
            response = requests.get(
                f"http://inventory:8000/inventory/{product_id}",
                params={"simulate_error": "true"} if simulate_error else None,
                timeout=3,
            )
            response.raise_for_status()
            return response.json()
    finally:
        context.detach(token)


@shop.get("/health")
@inventory_app.get("/health")
def health():
    return {"status": "ok"}


@inventory_app.get("/inventory/<int:product_id>")
def inventory(product_id):
    with tracer.start_as_current_span("inventory.read_stock") as span:
        span.set_attribute("shop.product_id", product_id)
        product = PRODUCTS.get(product_id)
    if product is None:
        return {"error": "Product not found"}, 404
    cohort = demo_cohort()
    endpoint = baggage.get_baggage(ENDPOINT_BAGGAGE)
    if endpoint in INVENTORY_CALLERS:
        trace.get_current_span().set_attribute(ENDPOINT_BAGGAGE, endpoint)
    else:
        endpoint = None
    if request.args.get("simulate_error") == "true":
        inventory_app.logger.error(
            "Simulated inventory failure product_id=%s shop_endpoint=%s demo_cohort=%s",
            product_id, endpoint, cohort,
        )
        return {"error": "Simulated inventory failure"}, 503
    inventory_app.logger.info(
        "Inventory checked product_id=%s shop_endpoint=%s demo_cohort=%s",
        product_id, endpoint, cohort,
    )
    return {"stock": product["stock"], "demo_cohort": cohort, "shop_endpoint": endpoint}


@shop.get("/")
def home():
    return render_template("shop.html", products=PRODUCTS, page="stock")


@shop.get("/checkout")
def checkout_page():
    return render_template("shop.html", products=PRODUCTS, page="checkout")


@shop.get("/api/products")
def products():
    return jsonify([{"id": key, **product} for key, product in PRODUCTS.items()])


@shop.get("/api/products/<int:product_id>")
def product_detail(product_id):
    product = PRODUCTS.get(product_id)
    if product is None:
        return {"error": "Product not found"}, 404
    return {"id": product_id, **product}


@shop.get("/api/products/<int:product_id>/stock")
def product_stock(product_id):
    if product_id not in PRODUCTS:
        return {"error": "Product not found"}, 404
    demo_cohort()
    try:
        availability = check_inventory(product_id)
    except requests.RequestException:
        shop.logger.exception("Inventory request failed for product_id=%s", product_id)
        return {"error": "Inventory unavailable"}, 502
    return {
        "id": product_id,
        "stock": availability["stock"],
        "inventory_endpoint": availability["shop_endpoint"],
    }


@shop.post("/api/checkout")
def checkout():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "Send a JSON object"}, 400
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    if type(product_id) is not int or type(quantity) is not int or quantity < 1:
        return {"error": "Send integer product_id and positive integer quantity"}, 400
    product = PRODUCTS.get(product_id)
    if product is None:
        return {"error": "Product not found"}, 404

    simulate_error = payload.get("simulate_error") is True
    cohort = demo_cohort()
    try:
        availability = check_inventory(product_id, simulate_error=simulate_error)
    except requests.RequestException:
        shop.logger.exception("Inventory request failed for product_id=%s", product_id)
        return {"error": "Inventory unavailable"}, 502

    if quantity > availability["stock"]:
        return {"error": "Insufficient stock"}, 409
    shop.logger.info("Demo checkout product_id=%s quantity=%s demo_cohort=%s",
                    product_id, quantity, cohort)
    return {
        "status": "simulated",
        "total_cents": quantity * product["price_cents"],
        "shop_cohort": cohort,
        "inventory_cohort": availability["demo_cohort"],
        "inventory_endpoint": availability["shop_endpoint"],
    }


if __name__ == "__main__":
    service = inventory_app if os.environ.get("APP_ROLE") == "inventory" else shop
    service.run(host="0.0.0.0", port=8000)
