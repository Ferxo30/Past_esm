from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    wv_qty = fields.Boolean(string="Quantity", default=True)
    wv_discount = fields.Boolean(string="Discount", default=True)
    wv_price = fields.Boolean(string="Price", default=True)
    wv_plusminus = fields.Boolean(string="+/- Button", default=True)
    wv_payment = fields.Boolean(string="Payment", default=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        """In Odoo 18, pos.config needs to provide the full payload expected by the
        POS frontend. Returning only custom fields breaks the POS loading flow.
        We therefore start from every readable field on pos.config and ensure our
        custom booleans are present.
        """
        fields_list = list(self.fields_get().keys())
        extra_fields = [
            "wv_qty",
            "wv_discount",
            "wv_price",
            "wv_plusminus",
            "wv_payment",
        ]
        for field_name in extra_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
