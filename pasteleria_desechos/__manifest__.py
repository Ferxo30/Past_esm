# -*- coding: utf-8 -*-
{
    "name": "Pastelería - Gestión de Desechos",
    "version": "18.0.2.1.0",
    "category": "Inventory",
    "summary": "Registro y aprobación jerárquica de desechos (impacto a inventario solo al confirmar) + registro desde POS.",
    "depends": ["stock", "point_of_sale", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/locations.xml",
        "views/desecho_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_desechos/static/src/js/desecho_button.js",
            "pasteleria_desechos/static/src/js/desecho_manager_button.js",
            "pasteleria_desechos/static/src/js/desecho_orders_screen.js",
            "pasteleria_desechos/static/src/xml/desecho_orders_screen.xml",
            "pasteleria_desechos/static/src/scss/desecho_popup.scss",
        ],
        "point_of_sale.assets": [
            "pasteleria_desechos/static/src/js/desecho_button.js",
            "pasteleria_desechos/static/src/js/desecho_manager_button.js",
            "pasteleria_desechos/static/src/js/desecho_orders_screen.js",
            "pasteleria_desechos/static/src/xml/desecho_orders_screen.xml",
            "pasteleria_desechos/static/src/scss/desecho_popup.scss",
        ],
    },
    "application": False,
    "license": "LGPL-3",
}