# -*- coding: utf-8 -*-
from odoo import fields, models


class PasteleriaCakeFractionReason(models.Model):
    _name = "pasteleria.cake.fraction.reason"
    _description = "Motivo de fraccionamiento"
    _order = "name"

    name = fields.Char(string="Motivo", required=True)
    active = fields.Boolean(default=True)
