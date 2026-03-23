# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    is_cake_slice_value = fields.Boolean(
        string="Es porción",
        help="Indica que este valor de variante representa una porción de pastel."
    )

    can_be_fraction_source_value = fields.Boolean(
        string="Permite fraccionamiento",
        help="Indica que este valor de variante puede usarse como origen para fraccionar un pastel completo."
    )

    expected_slice_min = fields.Integer(
        string="Porciones mínimas sugeridas",
        help="Cantidad mínima sugerida de porciones para este valor de variante."
    )

    expected_slice_max = fields.Integer(
        string="Porciones máximas sugeridas",
        help="Cantidad máxima sugerida de porciones para este valor de variante."
    )