# -*- coding: utf-8 -*-

def post_init_hook(env):
    env["pasteleria.pos.report.product.map"].sudo().action_rebuild_from_pos_products()