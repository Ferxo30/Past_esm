# -*- coding: utf-8 -*-

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    allow_internal_transfers = fields.Boolean(
        string="Permitir transferencias internas",
        help="Permite crear transferencias internas desde este punto de venta.",
        default=False,
    )

    transfer_operation_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operación para transferencias",
        domain="[('code', '=', 'internal')]",
        help="Tipo de operación interna que se usará para generar el traslado.",
    )

    transfer_source_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación origen para transferencias",
        domain="[('usage', '=', 'internal')]",
        help="Ubicación desde la cual este POS enviará producto.",
    )

    allowed_destination_pos_ids = fields.Many2many(
        "pos.config",
        "pasteleria_pos_transfer_allowed_dest_rel",
        "source_pos_id",
        "destination_pos_id",
        string="POS destino permitidos",
        help="Sucursales a las que este POS puede enviar producto.",
    )