from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_pos_expiry_warning_days = fields.Integer(
        string="Días de advertencia POS",
        default=2,
        help="Cantidad de días antes de vencer en los que el POS mostrará advertencia amarilla.",
    )

    @api.model
    def pos_get_expiry_snapshot(self, pos_config_id, product_ids=None):
        products = self.browse(product_ids) if product_ids else self.search([
            ("available_in_pos", "=", True),
            ("active", "=", True),
        ])
        return self.env["stock.lot"].pos_build_product_expiry_snapshot(pos_config_id, products.ids)