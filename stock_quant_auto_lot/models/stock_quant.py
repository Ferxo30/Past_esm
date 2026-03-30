import re

from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _auto_lot_sequence_code(self):
        return 'stock.lot.auto.quant'

    @api.model
    def _sanitize_auto_lot_prefix(self, value):
        value = (value or '').upper().strip()
        value = re.sub(r'[^A-Z0-9]+', '', value)
        return value[:12] or 'LOT'

    @api.model
    def _build_auto_lot_name(self, product):
        prefix = self._sanitize_auto_lot_prefix(product.default_code or product.display_name or 'LOT')
        date_part = fields.Date.context_today(self).strftime('%Y%m%d')
        sequence = self.env['ir.sequence'].sudo().next_by_code(self._auto_lot_sequence_code()) or '0001'
        return f'{prefix}-{date_part}-{sequence}'

    @api.model
    def _should_auto_create_lot_on_vals(self, product, qty):
        return bool(
            product
            and product.exists()
            and product.tracking == 'lot'
            and qty is not None
            and not float_is_zero(qty, precision_rounding=product.uom_id.rounding)
        )

    @api.model
    def _get_inventory_qty_from_vals(self, vals):
        if 'inventory_quantity_auto_apply' in vals:
            return vals.get('inventory_quantity_auto_apply')
        if 'inventory_quantity' in vals:
            return vals.get('inventory_quantity')
        return None

    @api.model
    def _create_auto_lot(self, product, location):
        company = location.company_id or self.env.company
        return self.env['stock.lot'].sudo().create({
            'name': self._build_auto_lot_name(product),
            'product_id': product.id,
            'company_id': company.id,
        })

    @api.model
    def _prepare_auto_lot_on_create_vals(self, vals):
        if vals.get('lot_id') or not vals.get('product_id') or not vals.get('location_id'):
            return vals

        qty = self._get_inventory_qty_from_vals(vals)
        product = self.env['product.product'].browse(vals['product_id'])
        if not self._should_auto_create_lot_on_vals(product, qty):
            return vals

        location = self.env['stock.location'].browse(vals['location_id'])
        lot = self._create_auto_lot(product, location)
        vals['lot_id'] = lot.id
        return vals

    def _assign_auto_lot_before_inventory_write(self, vals):
        qty = self._get_inventory_qty_from_vals(vals)
        if qty is None:
            return

        for quant in self.filtered(lambda q: q.product_id.tracking == 'lot' and not q.lot_id and q.location_id):
            if float_is_zero(qty, precision_rounding=quant.product_uom_id.rounding):
                continue
            lot = self._create_auto_lot(quant.product_id, quant.location_id)
            super(StockQuant, quant.sudo().with_context(
                inventory_mode=False,
                skip_auto_lot_generation=True,
            )).write({'lot_id': lot.id})

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_inventory_mode() and not self.env.context.get('skip_auto_lot_generation'):
            vals_list = [self._prepare_auto_lot_on_create_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if self._is_inventory_mode() and not self.env.context.get('skip_auto_lot_generation'):
            self._assign_auto_lot_before_inventory_write(vals)
        return super().write(vals)
