# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    pasteleria_pos_transfer_id = fields.Many2one(
        "pasteleria.pos.transfer",
        string="Transferencia POS",
        copy=False,
        index=True,
    )