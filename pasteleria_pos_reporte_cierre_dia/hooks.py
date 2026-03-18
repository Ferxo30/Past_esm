# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["pasteleria.pos.report.product.map"].action_rebuild_from_pos_products()