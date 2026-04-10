import re
from datetime import date, datetime

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
    def _production_date_field_names(self):
        explicit_candidates = [
            'production_date',
            'fecha_produccion',
            'date_production',
            'prod_date',
            'x_production_date',
            'x_fecha_produccion',
            'x_studio_production_date',
            'x_studio_fecha_de_produccion',
            'x_studio_fecha_produccion',
            'x_studio_date_production',
        ]
        fields_map = self._fields
        result = [
            name for name in explicit_candidates
            if name in fields_map and fields_map[name].type in ('date', 'datetime')
        ]
        if result:
            return result

        dynamic_matches = []
        for name, field in fields_map.items():
            if field.type not in ('date', 'datetime'):
                continue
            lname = name.lower()
            if ('production' in lname or 'produccion' in lname) and 'expiration' not in lname and 'caduc' not in lname:
                dynamic_matches.append(name)
        return dynamic_matches

    @api.model
    def _coerce_value_for_field(self, field_name, base_date):
        field = self._fields.get(field_name)
        if not field:
            return False
        if field.type == 'date':
            return fields.Date.to_string(base_date)
        return fields.Datetime.to_string(datetime.combine(base_date, datetime.min.time()))

    @api.model
    def _extract_date_from_value(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return fields.Date.to_date(value)
            except Exception:
                try:
                    return fields.Datetime.to_datetime(value).date()
                except Exception:
                    return False
        return False

    @api.model
    def _looks_like_placeholder_production_date(self, value):
        parsed = self._extract_date_from_value(value)
        return bool(parsed and parsed.month == 12 and parsed.day == 31)

    @api.model
    def _inventory_date_field_name(self):
        return 'inventory_date' if 'inventory_date' in self._fields else False

    @api.model
    def _today_inventory_date_string(self):
        return fields.Date.to_string(fields.Date.context_today(self))

    @api.model
    def _normalize_quant_inventory_date_vals(self, vals, quant=None, force_default=False):
        vals = dict(vals or {})
        field_name = self._inventory_date_field_name()
        if not field_name:
            return vals

        today = fields.Date.context_today(self)
        if field_name in vals:
            current = vals.get(field_name)
            if not current or self._looks_like_placeholder_production_date(current):
                vals[field_name] = fields.Date.to_string(today)
            return vals

        if force_default:
            vals[field_name] = fields.Date.to_string(today)
            return vals

        if quant:
            current = getattr(quant, field_name, False)
            if not current or self._looks_like_placeholder_production_date(current):
                vals[field_name] = fields.Date.to_string(today)
        return vals

    @api.model
    def _get_inventory_base_date(self, vals=None, quant=None):
        vals = vals or {}
        for field_name in self._production_date_field_names():
            if field_name in vals and vals.get(field_name):
                parsed = self._extract_date_from_value(vals[field_name])
                if parsed and not self._looks_like_placeholder_production_date(parsed):
                    return parsed
        if quant:
            for field_name in self._production_date_field_names():
                parsed = self._extract_date_from_value(getattr(quant, field_name, False))
                if parsed and not self._looks_like_placeholder_production_date(parsed):
                    return parsed
        return fields.Date.context_today(self)

    @api.model
    def _normalize_quant_production_date_vals(self, vals, product=None, quant=None):
        vals = dict(vals or {})
        product = product or (quant.product_id if quant else False)
        if not product or product.tracking != 'lot':
            return vals

        production_fields = self._production_date_field_names()
        if not production_fields:
            return vals

        today = fields.Date.context_today(self)
        explicit_name = next((fname for fname in production_fields if fname in vals), False)
        if explicit_name:
            if self._looks_like_placeholder_production_date(vals.get(explicit_name)):
                vals[explicit_name] = self._coerce_value_for_field(explicit_name, today)
            return vals

        for field_name in production_fields:
            vals[field_name] = self._coerce_value_for_field(field_name, today)
        return vals

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
    def _create_auto_lot(self, product, location, vals=None, quant=None):
        company = location.company_id or self.env.company
        base_date = self._get_inventory_base_date(vals=vals, quant=quant)
        lot_vals = {
            'name': self._build_auto_lot_name(product),
            'product_id': product.id,
            'company_id': company.id,
        }
        return self.env['stock.lot'].sudo().with_context(
            auto_lot_manage_production_date=True,
            auto_lot_preserve_production_date=True,
            auto_lot_base_date=fields.Date.to_string(base_date),
        ).create(lot_vals)

    @api.model
    def _prepare_auto_lot_on_create_vals(self, vals):
        vals = self._normalize_quant_inventory_date_vals(vals, force_default=True)
        if vals.get('lot_id') or not vals.get('product_id') or not vals.get('location_id'):
            return vals

        qty = self._get_inventory_qty_from_vals(vals)
        product = self.env['product.product'].browse(vals['product_id'])
        vals = self._normalize_quant_production_date_vals(vals, product=product)
        if not self._should_auto_create_lot_on_vals(product, qty):
            return vals

        location = self.env['stock.location'].browse(vals['location_id'])
        lot = self._create_auto_lot(product, location, vals=vals)
        vals['lot_id'] = lot.id
        return vals

    def _assign_auto_lot_before_inventory_write(self, vals):
        qty = self._get_inventory_qty_from_vals(vals)
        if qty is None:
            return

        for quant in self.filtered(lambda q: q.product_id.tracking == 'lot' and not q.lot_id and q.location_id):
            if float_is_zero(qty, precision_rounding=quant.product_uom_id.rounding):
                continue
            lot = self._create_auto_lot(quant.product_id, quant.location_id, vals=vals, quant=quant)
            base_date = self._get_inventory_base_date(vals=vals, quant=quant)
            write_vals = {'lot_id': lot.id}
            for field_name in self._production_date_field_names():
                if field_name not in vals:
                    write_vals[field_name] = self._coerce_value_for_field(field_name, base_date)
                elif self._looks_like_placeholder_production_date(vals.get(field_name)):
                    write_vals[field_name] = self._coerce_value_for_field(field_name, base_date)
            super(StockQuant, quant.sudo().with_context(
                inventory_mode=False,
                skip_auto_lot_generation=True,
            )).write(write_vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._is_inventory_mode() and self._inventory_date_field_name() in fields_list:
            current = res.get('inventory_date')
            if not current or self._looks_like_placeholder_production_date(current):
                res['inventory_date'] = self._today_inventory_date_string()
        return res

    def action_apply_inventory(self):
        inventory_date_field = self._inventory_date_field_name()
        preserved_dates = {}
        if inventory_date_field:
            for quant in self:
                current = getattr(quant, inventory_date_field, False)
                if not current or self._looks_like_placeholder_production_date(current):
                    current = self._today_inventory_date_string()
                else:
                    current = fields.Date.to_string(self._extract_date_from_value(current))
                preserved_dates[quant.id] = current

        result = super().action_apply_inventory()

        if preserved_dates and inventory_date_field:
            quants_to_restore = self.browse(list(preserved_dates))
            for quant in quants_to_restore.exists():
                value = preserved_dates.get(quant.id)
                if value and fields.Date.to_string(quant.inventory_date) != value:
                    super(StockQuant, quant.sudo().with_context(
                        inventory_mode=False,
                        skip_auto_lot_generation=True,
                    )).write({inventory_date_field: value})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_inventory_mode() and not self.env.context.get('skip_auto_lot_generation'):
            vals_list = [self._prepare_auto_lot_on_create_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if self._is_inventory_mode() and not self.env.context.get('skip_auto_lot_generation'):
            normalized_vals = dict(vals)
            sample_quant = self[:1]
            if sample_quant:
                normalized_vals = self._normalize_quant_inventory_date_vals(
                    normalized_vals,
                    quant=sample_quant,
                    force_default=not bool(self),
                )
            if any(q.product_id.tracking == 'lot' and not q.lot_id for q in self):
                sample_quant = next((q for q in self if q.product_id.tracking == 'lot' and not q.lot_id), False)
                normalized_vals = self._normalize_quant_production_date_vals(
                    normalized_vals,
                    quant=sample_quant,
                )
            self._assign_auto_lot_before_inventory_write(normalized_vals)
            return super().write(normalized_vals)
        return super().write(vals)
