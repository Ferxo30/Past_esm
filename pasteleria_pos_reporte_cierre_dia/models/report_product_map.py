# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _


class PasteleriaPosReportProductMap(models.Model):
    _name = "pasteleria.pos.report.product.map"
    _description = "Mapa de productos POS para reporte final del día"
    _order = "category_name, family_name, variant_normalized, product_id"

    product_id = fields.Many2one("product.product", string="Producto", required=True, ondelete="cascade", index=True)
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id", string="Plantilla", store=True)
    product_display_name = fields.Char(related="product_id.display_name", string="Nombre", store=True)
    default_code = fields.Char(related="product_id.default_code", string="Referencia", store=True)
    active = fields.Boolean(related="product_id.active", store=True)
    available_in_pos = fields.Boolean(related="product_id.available_in_pos", store=True)

    pos_category_id = fields.Many2one("pos.category", string="Categoría POS")
    category_name = fields.Char(string="Categoría")
    family_name = fields.Char(string="Familia", required=True)
    variant_raw = fields.Char(string="Variante detectada")
    variant_normalized = fields.Selection(
        [("pq", "Pq"), ("gr", "Gr"), ("p", "P"), ("other", "Otra")],
        string="Variante normalizada",
        default="other",
        required=True,
    )
    include_in_report = fields.Boolean(string="Incluir en reporte", default=True)
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "unique_product_report_map",
            "unique(product_id)",
            "Ya existe un registro de mapeo para este producto.",
        )
    ]

    @api.model
    def action_rebuild_from_pos_products(self):
        Product = self.env["product.product"]
        maps = self.search([])
        existing_by_product = {m.product_id.id: m for m in maps}

        products = Product.search([
            ("available_in_pos", "=", True),
            ("active", "=", True),
        ])

        seen_ids = set()
        for product in products:
            seen_ids.add(product.id)
            values = self._prepare_map_vals_from_product(product)
            if product.id in existing_by_product:
                existing_by_product[product.id].write(values)
            else:
                self.create(values)

        obsolete = maps.filtered(lambda m: m.product_id.id not in seen_ids)
        if obsolete:
            obsolete.unlink()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Mapa actualizado"),
                "message": _("Se reconstruyó el mapa desde los productos disponibles en POS."),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _prepare_map_vals_from_product(self, product):
        family_name, variant_raw, variant_normalized = self._infer_family_and_variant_from_product(product)

        pos_category = False
        tmpl = product.product_tmpl_id

        if hasattr(tmpl, "pos_categ_ids") and tmpl.pos_categ_ids:
            pos_category = tmpl.pos_categ_ids[:1]
        elif hasattr(product, "pos_categ_ids") and product.pos_categ_ids:
            pos_category = product.pos_categ_ids[:1]

        category_name = (
            pos_category.display_name
            if pos_category
            else (product.categ_id.display_name if product.categ_id else _("Sin categoría"))
        )

        return {
            "product_id": product.id,
            "pos_category_id": pos_category.id if pos_category else False,
            "category_name": category_name,
            "family_name": family_name or product.product_tmpl_id.name or product.display_name,
            "variant_raw": variant_raw,
            "variant_normalized": variant_normalized,
            "include_in_report": True,
        }

    @api.model
    def _infer_family_and_variant_from_product(self, product):
        attr_names = []
        if hasattr(product, "product_template_attribute_value_ids"):
            attr_names = [
                (ptav.product_attribute_value_id.name or "").strip()
                for ptav in product.product_template_attribute_value_ids
                if ptav.product_attribute_value_id
            ]

        for attr_name in attr_names:
            normalized = self._normalize_variant_name(attr_name)
            if normalized != "other":
                family = product.product_tmpl_id.name or product.display_name
                return family.strip(), attr_name, normalized

        full_name = " ".join(filter(None, [product.display_name, product.name, product.product_tmpl_id.name]))
        normalized = self._normalize_variant_name(full_name)

        raw = False
        family = product.product_tmpl_id.name or product.display_name or product.name
        if normalized != "other":
            token_pattern = r'(?i)(?:\bPq\b|\bGr\b|\bP\b|peque(?:ñ|n)o|grande|porci(?:ó|o)n)'
            match = re.search(token_pattern, full_name or "")
            raw = match.group(0) if match else False
            cleaned = re.sub(
                r'(?i)\s*[-/()]?\s*(?:Pq|Gr|P|peque(?:ñ|n)o|grande|porci(?:ó|o)n)\s*$',
                '',
                family
            ).strip(' -_/')
            if cleaned:
                family = cleaned

        return family.strip(), raw, normalized

    @api.model
    def _normalize_variant_name(self, text):
        value = (text or "").strip().lower()
        if not value:
            return "other"

        patterns = {
            "pq": [r"\bpq\b", r"peque(?:ñ|n)o", r"10\s*porciones", r"12\s*porciones"],
            "gr": [r"\bgr\b", r"grande", r"15\s*porciones", r"20\s*porciones"],
            "p": [r"\bp\b", r"porci(?:ó|o)n", r"slice"],
        }
        for normalized, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, value, flags=re.IGNORECASE):
                    return normalized
        return "other"