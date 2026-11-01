#!/usr/bin/env python3
"""Routes trang HTML: / (inbox), /orders, /settings."""
from flask import Blueprint, render_template

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def inbox():
    return render_template("inbox.html")


@views_bp.get("/orders")
def orders():
    return render_template("orders.html")


@views_bp.get("/products")
def products():
    return render_template("products.html")


@views_bp.get("/customers")
def customers():
    return render_template("customers.html")


@views_bp.get("/settings")
def settings():
    return render_template("settings.html")
