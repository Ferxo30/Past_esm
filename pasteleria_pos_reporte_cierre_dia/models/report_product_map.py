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
        [
            ("p", "Porción"),
            ("pq", "Pequeño"),
            ("gr", "Grande 12-16"),
            ("xg", "25-30 porciones"),
            ("xg40", "40 porciones"),
            ("pl40_45", "40-45 porciones"),
            ("pl55_60", "55-60 porciones"),
            ("pl100", "100 porciones"),
            ("other", "Otra"),
        ],
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

    def action_rebuild_from_pos_products(self):
        self = self.sudo()
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

        if pos_category:
            category_name = pos_category.display_name
        elif product.categ_id:
            category_name = product.categ_id.display_name
        else:
            category_name = _("Sin categoría POS")

        if not category_name or str(category_name).strip().lower() == "all":
            category_name = _("Sin categoría POS")

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
        tmpl = product.product_tmpl_id
        family = tmpl.name or product.display_name or product.name
        variant_raw = False
        variant_normalized = "other"

        ptav_records = getattr(product, "product_template_attribute_value_ids", False) or self.env["product.template.attribute.value"]

        size_attr_values = []
        for ptav in ptav_records:
            attr_name = (ptav.attribute_id.name or "").strip().lower() if ptav.attribute_id else ""
            value_name = (ptav.product_attribute_value_id.name or "").strip() if ptav.product_attribute_value_id else ""
            if attr_name.startswith("tamaño") or attr_name.startswith("tamano"):
                size_attr_values.append(value_name)

        for value_name in size_attr_values:
            normalized = self._normalize_variant_name(value_name)
            if normalized != "other":
                variant_raw = value_name
                variant_normalized = normalized
                return family.strip(), variant_raw, variant_normalized

        full_name = " ".join(filter(None, [product.display_name, product.name, tmpl.name]))
        variant_normalized = self._normalize_variant_name(full_name)

        if variant_normalized != "other":
            token_pattern = (
                r"(?i)"
                r"("
                    r"\bporci(?:ó|o)?n\b|"
                    r"\b1\s*porci(?:ó|o)?n\b|"
                    r"\b5\s*porciones?\b|"
                    r"\bpeque(?:ñ|n)o(?:\s*5)?\b|"
                    r"\bpeque(?:ñ|n)o\s*8\s*-\s*10\b|"
                    r"\b8\s*-\s*10\b|"
                    r"\bcompleto\b|"
                    r"\bcompleto\s*q\b|"
                    r"\bgrande\s*12\s*-\s*16\b|"
                    r"\b12\s*-\s*16\b|"
                    r"\b25\s*-\s*30\s*porciones?\b|"
                    r"\b25\s*-\s*30\b|"
                    r"\b40\s*porciones?\b|"
                    r"\b40\s*-\s*45\s*porciones?\b|"
                    r"\b40\s*-\s*45\b|"
                    r"\b55\s*-\s*60\s*porciones?\b|"
                    r"\b55\s*-\s*60\b|"
                    r"\b100\s*porciones?\b|"
                    r"\b100\b"
                r")"
            )
            match = re.search(token_pattern, full_name or "")
            variant_raw = match.group(0) if match else False

        return family.strip(), variant_raw, variant_normalized

    @api.model
    def _normalize_variant_name(self, text):
        value = (text or "").strip().lower()
        if not value:
            return "other"

        patterns = {
            "p": [
                r"\bporci(?:ó|o)?n\b",
                r"\b1\s*porci(?:ó|o)?n\b",
            ],
            # TODO lo pequeño entra a pq:
            # - 5 porciones
            # - pequeño 5
            # - pequeño
            # - pequeño 8-10
            # - completo / completo q
            "pq": [
                r"\b5\s*porciones?\b",
                r"\bpeque(?:ñ|n)o\s*5\b",
                r"\bpeque(?:ñ|n)o\b",
                r"\bpeque(?:ñ|n)o\s*8\s*-\s*10\b",
                r"\b8\s*-\s*10\b",
                r"\bcompleto\b",
                r"\bcompleto\s*q\b",
            ],
            "gr": [
                r"\bgrande\s*12\s*-\s*16\b",
                r"\b12\s*-\s*16\b",
            ],
            "xg": [
                r"\b25\s*-\s*30\s*porciones?\b",
                r"\b25\s*-\s*30\b",
            ],
            "xg40": [
                r"\b40\s*porciones?\b",
            ],
            "pl40_45": [
                r"\b40\s*-\s*45\s*porciones?\b",
                r"\b40\s*-\s*45\b",
            ],
            "pl55_60": [
                r"\b55\s*-\s*60\s*porciones?\b",
                r"\b55\s*-\s*60\b",
            ],
            "pl100": [
                r"\b100\s*porciones?\b",
                r"\b100\b",
            ],
        }

        for normalized, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, value, flags=re.IGNORECASE):
                    return normalized

        return "other"