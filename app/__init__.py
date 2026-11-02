#!/usr/bin/env python3
"""ShopDesk — app web quản lý bán hàng cho 2 shop dép (Dép Hana & Bé Đan).

App THỦ CÔNG cho nhân viên/chủ shop. Chạy độc lập, không động vào hệ thống
automation inbox hiện tại (daemon instant_reply.py + cron).
"""
import os

from flask import Flask

from . import config as config_mod
from . import db as db_mod


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"),
    )
    app.config["JSON_AS_ASCII"] = False

    # Khởi tạo config + DB ngay khi app khởi động
    config_mod.load_config()
    db_mod.init_db()

    from .views import views_bp
    from .pages import pages_bp
    from .orders import orders_bp
    from .shipping import shipping_bp
    from .fbconnect import fbconnect_bp
    from .products import products_bp, init_products
    from .customers import customers_bp, init_customers
    from .tags import tags_bp, init_conversation_tags

    app.register_blueprint(views_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(shipping_bp)
    app.register_blueprint(fbconnect_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(tags_bp)

    # Bảng mới: products, customers, conversation_tags (idempotent + seed)
    init_products()
    init_customers()
    init_conversation_tags()

    @app.errorhandler(404)
    def not_found(e):
        return {"ok": False, "error_vi": "Không tìm thấy đường dẫn yêu cầu."}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {"ok": False, "error_vi": "Lỗi máy chủ nội bộ. Vui lòng thử lại."}, 500

    return app
