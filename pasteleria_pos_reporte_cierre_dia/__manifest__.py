# -*- coding: utf-8 -*-
{
    "name": "Pastelería POS - Reporte Cierre Día",
    "version": "18.0.2.0.0",
    "summary": "Genera y almacena reporte final del día por sesión POS",
    "category": "Point of Sale",
    "author": "Tu Equipo",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "stock",
        "product",
        "pasteleria_desechos",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/report_product_map_views.xml",
        "views/daily_report_views.xml",
        "views/menu_views.xml",
        "report/daily_report_report.xml",
        "report/daily_report_template.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}