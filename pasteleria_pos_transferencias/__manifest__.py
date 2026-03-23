# -*- coding: utf-8 -*-
{
    "name": "Pastelería POS - Transferencias entre sucursales",
    "version": "18.0.1.0.0",
    "summary": "Transferencias internas entre puntos de venta desde POS",
    "category": "Point of Sale",
    "author": "Proyecto Pastelería",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "stock",
        "product",
        "mail",
        "pasteleria_desechos",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/res_config_settings_views.xml",
        "views/pos_transfer_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_pos_transferencias/static/src/js/transfer_button.js",
            "pasteleria_pos_transferencias/static/src/js/transfer_popup.js",
            "pasteleria_pos_transferencias/static/src/js/transfer_service.js",
            "pasteleria_pos_transferencias/static/src/xml/transfer_popup.xml",
            "pasteleria_pos_transferencias/static/src/scss/transfer.scss",
        ],
    },
    "installable": True,
    "application": False,
}