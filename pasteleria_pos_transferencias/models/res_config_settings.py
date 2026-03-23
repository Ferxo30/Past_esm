# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_transfer_allow_internal_transfers = fields.Boolean(
        string="Permitir transferencias internas",
        related="pos_config_id.allow_internal_transfers",
        readonly=False,
    )

    pos_transfer_operation_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operación para transferencias",
        related="pos_config_id.transfer_operation_type_id",
        readonly=False,
    )

    pos_transfer_source_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación origen para transferencias",
        related="pos_config_id.transfer_source_location_id",
        readonly=False,
    )

    pos_transfer_allowed_destination_pos_ids = fields.Many2many(
        "pos.config",
        string="POS destino permitidos",
        related="pos_config_id.allowed_destination_pos_ids",
        readonly=False,
    )