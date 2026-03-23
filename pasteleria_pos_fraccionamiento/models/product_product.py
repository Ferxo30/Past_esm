# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_cake_slice = fields.Boolean(
        string="Es porción",
        help="Marcar en la variante que representa la porción del pastel.",
    )
    can_be_fraction_source = fields.Boolean(
        string="Se puede fraccionar",
        help="Marcar en variantes enteras que pueden convertirse en porciones.",
    )
    expected_slice_min = fields.Integer(
        string="Porciones mínimas sugeridas",
        help="Solo informativo. Se usa para advertencias en el fraccionamiento.",
    )
    expected_slice_max = fields.Integer(
        string="Porciones máximas sugeridas",
        help="Solo informativo. Se usa para advertencias en el fraccionamiento.",
    )
    cake_slice_product_id = fields.Many2one(
        "product.product",
        string="Variante porción vinculada",
        compute="_compute_cake_slice_product_id",
        store=False,
        help="Variante del mismo producto plantilla marcada como porción.",
    )

    @api.depends("product_tmpl_id.product_variant_ids.is_cake_slice")
    def _compute_cake_slice_product_id(self):
        for product in self:
            candidates = product.product_tmpl_id.product_variant_ids.filtered(lambda p: p.is_cake_slice)
            product.cake_slice_product_id = candidates[:1].id if candidates else False

    @api.constrains("is_cake_slice", "product_tmpl_id")
    def _check_single_slice_variant_per_template(self):
        for product in self.filtered("is_cake_slice"):
            siblings = product.product_tmpl_id.product_variant_ids.filtered(lambda p: p.is_cake_slice)
            if len(siblings) > 1:
                raise ValidationError(_(
                    "Solo puede existir una variante marcada como porción por producto plantilla."
                ))

    @api.constrains("expected_slice_min", "expected_slice_max")
    def _check_expected_slice_range(self):
        for product in self:
            if (
                product.expected_slice_min
                and product.expected_slice_max
                and product.expected_slice_min > product.expected_slice_max
            ):
                raise ValidationError(_("La cantidad mínima sugerida no puede ser mayor que la máxima."))

    @api.constrains("is_cake_slice", "can_be_fraction_source")
    def _check_slice_and_source_flags(self):
        for product in self:
            if product.is_cake_slice and product.can_be_fraction_source:
                raise ValidationError(_("Una misma variante no puede ser porción y origen de fraccionamiento a la vez."))

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        extra_fields = [
            "is_cake_slice",
            "can_be_fraction_source",
            "expected_slice_min",
            "expected_slice_max",
            "cake_slice_product_id",
        ]
        for field_name in extra_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list