# -*- coding: utf-8 -*-
from odoo import fields, models


class PasteleriaPosReportTemplateLine(models.Model):
    _name = "pasteleria.pos.report.template.line"
    _description = "Plantilla de líneas para reporte final del día"
    _order = "sequence asc, id asc"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    name = fields.Char(string="Descripción", required=True)

    product_pq_id = fields.Many2one(
        "product.product",
        string="Producto variante Pq",
        domain=[("available_in_pos", "=", True)],
    )
    product_gr_id = fields.Many2one(
        "product.product",
        string="Producto variante Gr",
        domain=[("available_in_pos", "=", True)],
    )
    product_p_id = fields.Many2one(
        "product.product",
        string="Producto variante P",
        domain=[("available_in_pos", "=", True)],
    )
    notes = fields.Text(string="Notas")
