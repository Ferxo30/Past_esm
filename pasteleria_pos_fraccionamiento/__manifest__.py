# -*- coding: utf-8 -*-
{
    "name": "Pastelería - Fraccionamiento de Pasteles",
    "version": "18.0.1.1.0",
    "category": "Inventory",
    "summary": "Fraccionamiento de pasteles completos a porciones con trazabilidad e impacto en inventario.",
    "depends": [
        "stock",
        "product",
        "point_of_sale",
        "mail",
        "pasteleria_desechos",
        "pasteleria_pos_lot_expiry_guard",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/product_product_views.xml",
        "views/product_template_attribute_value_views.xml",
        "views/cake_fraction_reason_views.xml",
        "views/cake_fraction_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_pos_fraccionamiento/static/src/js/*.js",
            "pasteleria_pos_fraccionamiento/static/src/xml/*.xml",
            "pasteleria_pos_fraccionamiento/static/src/scss/*.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
