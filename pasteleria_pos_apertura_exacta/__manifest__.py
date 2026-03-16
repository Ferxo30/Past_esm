{
    "name": "Pastelería POS Apertura Exacta",
    "version": "18.0.1.0.0",
    "summary": "Valida que la apertura de caja del POS coincida exactamente con el monto esperado",
    "description": """
Control mínimo para POS en Odoo 18.

Este módulo NO reemplaza la lógica nativa de sesiones del POS.
Solamente:
- agrega un monto esperado configurable por punto de venta;
- valida en backend que el monto de apertura coincida exactamente;
- deja que Odoo siga manejando la sesión y la apertura de forma nativa.
    """,
    "author": "OpenAI / Tecnodyne",
    "category": "Point of Sale",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "pasteleria_desechos",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pasteleria_pos_apertura_exacta/static/src/js/opening_validation_notice.js",
        ],
    },
    "installable": True,
    "application": False,
}
