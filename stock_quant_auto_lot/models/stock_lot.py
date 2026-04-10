from datetime import date, datetime, time, timedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model
    def _production_date_field_names(self):
        """Return candidate field names that likely store a production date.

        This is intentionally tolerant because some databases use Studio/custom
        fields such as ``x_studio_fecha_de_produccion``.
        """
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
        return fields.Datetime.to_string(datetime.combine(base_date, time.min))

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
    def _get_context_base_date(self):
        value = self.env.context.get('auto_lot_base_date')
        parsed = self._extract_date_from_value(value)
        return parsed or fields.Date.context_today(self)

    @api.model
    def _get_product_for_date_rules(self, vals=None):
        vals = vals or {}
        product = False
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
        elif getattr(self, 'product_id', False):
            product = self.product_id
        return product if product and product.exists() else False

    @api.model
    def _get_product_expiry_days(self, product, attr_names):
        if not product:
            return 0
        candidates = [product, getattr(product, 'product_tmpl_id', False)]
        for record in candidates:
            if not record:
                continue
            for attr_name in attr_names:
                if hasattr(record, attr_name):
                    value = getattr(record, attr_name)
                    if value:
                        return int(value)
        return 0

    @api.model
    def _prepare_auto_lot_date_defaults(self, vals=None, base_date=None):
        vals = dict(vals or {})
        base_date = self._extract_date_from_value(base_date) or self._get_context_base_date()

        # 1) Set production date defaults only if not already provided.
        for field_name in self._production_date_field_names():
            if not vals.get(field_name) or self._looks_like_placeholder_production_date(vals.get(field_name)):
                vals[field_name] = self._coerce_value_for_field(field_name, base_date)

        # 2) If standard expiration fields exist and are empty, derive them from
        #    the chosen base date using the product's expiration configuration.
        product = self._get_product_for_date_rules(vals)
        if not product:
            return vals

        mapping = [
            ('life_date', ('expiration_time', 'life_time')),
            ('use_date', ('use_time',)),
            ('removal_date', ('removal_time',)),
            ('alert_date', ('alert_time',)),
        ]
        for field_name, product_attrs in mapping:
            if field_name not in self._fields or vals.get(field_name):
                continue
            days = self._get_product_expiry_days(product, product_attrs)
            if not days:
                continue
            target_date = base_date + timedelta(days=days)
            vals[field_name] = fields.Datetime.to_string(datetime.combine(target_date, time.min))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('auto_lot_manage_production_date'):
            vals_list = [self._prepare_auto_lot_date_defaults(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('auto_lot_preserve_production_date'):
            return super().write(vals)

        # Preserve any explicit production date the user passes and, if present,
        # align the standard expiration dates with that manual date without
        # overwriting values explicitly supplied in vals.
        production_fields = self._production_date_field_names()
        provided_prod_field = next((fname for fname in production_fields if fname in vals), False)
        explicit_prod_value = vals.get(provided_prod_field) if provided_prod_field else False

        if explicit_prod_value:
            if self._looks_like_placeholder_production_date(explicit_prod_value):
                base_date = self._get_context_base_date()
                vals[provided_prod_field] = self._coerce_value_for_field(provided_prod_field, base_date)
            else:
                parsed = self._extract_date_from_value(explicit_prod_value)
                base_date = parsed or self._get_context_base_date()

            vals = self._prepare_auto_lot_date_defaults(vals, base_date=base_date)

        return super().write(vals)
