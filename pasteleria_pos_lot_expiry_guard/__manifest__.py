{
    "name": "Pastelería POS - Lotes y Caducidad",
    "version": "18.0.1.0.0",
    "summary": "Semáforo de lotes, selección automática FEFO visual y bloqueo de venta de lotes vencidos en POS",
    "author": "OpenAI",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "depends": [
        "point_of_sale",
        "stock",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_pos_lot_expiry_guard/static/src/js/lot_expiry_service.js",
            "pasteleria_pos_lot_expiry_guard/static/src/js/payment_screen_block_patch.js",
            "pasteleria_pos_lot_expiry_guard/static/src/js/product_card_badge_patch.js",
            "pasteleria_pos_lot_expiry_guard/static/src/js/orderline_badge_patch.js",

            "pasteleria_pos_lot_expiry_guard/static/src/js/select_lot_popup_patch.js",

            "pasteleria_pos_lot_expiry_guard/static/src/xml/product_card_badge.xml",
            "pasteleria_pos_lot_expiry_guard/static/src/xml/orderline_badge.xml",
            "pasteleria_pos_lot_expiry_guard/static/src/xml/select_lot_popup_forward.xml",
            "pasteleria_pos_lot_expiry_guard/static/src/xml/edit_list_input_badge.xml",

            "pasteleria_pos_lot_expiry_guard/static/src/scss/lot_expiry.scss",

            "pasteleria_pos_lot_expiry_guard/static/src/js/product_attribute_badge_patch.js",
            "pasteleria_pos_lot_expiry_guard/static/src/xml/product_attribute_badge.xml",
        ],
    },
    "installable": True,
    "application": False,
}