# -*- coding: utf-8 -*-
{
    "name": "Pastelería POS - Recargar Recibo",
    "version": "18.0.1.1.0",
    "summary": "Agrega un botón en el POS para recargar visualmente el recibo y mostrar confirmación visible de la recarga.",
    "category": "Point of Sale",
    "author": "Proyecto Pastelería",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_pos_recargar_recibo/static/src/js/receipt_reload_button.js",
            "pasteleria_pos_recargar_recibo/static/src/scss/receipt_reload_button.scss",
        ],
    },
    "installable": True,
    "application": False,
}
