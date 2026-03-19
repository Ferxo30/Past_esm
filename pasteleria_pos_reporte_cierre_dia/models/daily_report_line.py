# -*- coding: utf-8 -*-
from odoo import fields, models


class PasteleriaPosDailyReportLine(models.Model):
    _name = "pasteleria.pos.daily.report.line"
    _description = "Línea Reporte Final del Día POS"
    _order = "sequence asc, id asc"

    report_id = fields.Many2one(
        "pasteleria.pos.daily.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(string="Secuencia", default=10)

    line_type = fields.Selection(
        [
            ("category", "Categoría"),
            ("family", "Familia"),
            ("subtotal", "Subtotal"),
        ],
        string="Tipo",
        default="family",
        required=True,
    )

    category_name = fields.Char(string="Categoría")
    display_name = fields.Char(string="Descripción", required=True)

    exist_e = fields.Float(string="Exist. E")
    exist_pq = fields.Float(string="Exist. Pq")
    exist_gr = fields.Float(string="Exist. Gr")
    exist_p = fields.Float(string="Exist. P")

    income_e = fields.Float(string="Ing. E")
    income_pq = fields.Float(string="Ing. Pq")
    income_gr = fields.Float(string="Ing. Gr")
    income_p = fields.Float(string="Ing. P")

    sales_e = fields.Float(string="Venta E")
    sales_pq = fields.Float(string="Venta Pq")
    sales_gr = fields.Float(string="Venta Gr")
    sales_p = fields.Float(string="Venta P")

    sales_amount_q = fields.Monetary(
        string="VTA-Q",
        currency_field="currency_id",
    )

    final_e = fields.Float(string="Saldo E")
    final_pq = fields.Float(string="Saldo Pq")
    final_gr = fields.Float(string="Saldo Gr")
    final_p = fields.Float(string="Saldo P")

    currency_id = fields.Many2one(
        related="report_id.currency_id",
        store=True,
    )