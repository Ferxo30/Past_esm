# -*- coding: utf-8 -*-
{
    "name": "Pastelería POS - Reporte Cierre Día",
    "version": "18.0.3.0.0",
    "summary": "Reporte final del día por sesión POS, agrupado por categoría y familia de producto.",
    "category": "Point of Sale",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "stock",
        "product",
        "mail",
        "pasteleria_desechos",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/report_product_map_views.xml",
        "views/daily_report_views.xml",
        "views/menu_views.xml",
        "report/daily_report_report.xml",
        "report/daily_report_template.xml",
    ],
    "application": False,
    "installable": True,
}
