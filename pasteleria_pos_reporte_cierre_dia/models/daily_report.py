# -*- coding: utf-8 -*-
import base64
import io
import json
from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PasteleriaPosDailyReport(models.Model):
    _name = "pasteleria.pos.daily.report"
    _description = "Reporte Final del Día POS"
    _order = "report_date desc, id desc"

    name = fields.Char(string="Nombre", required=True, default="Nuevo")
    session_id = fields.Many2one("pos.session", string="Sesión POS", required=True, ondelete="cascade", index=True)
    config_id = fields.Many2one(related="session_id.config_id", store=True, string="Punto de Venta")
    company_id = fields.Many2one(related="session_id.company_id", store=True, string="Compañía")
    user_id = fields.Many2one("res.users", string="Usuario cierre", required=True, default=lambda self: self.env.user)
    report_date = fields.Date(string="Fecha reporte", required=True, default=fields.Date.context_today)
    date_open = fields.Datetime(string="Apertura")
    date_close = fields.Datetime(string="Cierre")
    total_amount_q = fields.Monetary(string="Total Q", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("generated", "Generado"), ("error", "Error")],
        default="draft",
        required=True,
    )

    line_ids = fields.One2many("pasteleria.pos.daily.report.line", "report_id", string="Líneas")

    excel_file = fields.Binary(string="Archivo Excel", attachment=True)
    excel_filename = fields.Char(string="Nombre Excel")
    pdf_file = fields.Binary(string="Archivo PDF", attachment=True)
    pdf_filename = fields.Char(string="Nombre PDF")
    summary_text = fields.Text(string="Resumen")

    report_payload = fields.Text(string="Payload reporte")

    _sql_constraints = [(
        "unique_session_report",
        "unique(session_id)",
        "Ya existe un reporte final del día para esta sesión POS.",
    )]

    VARIANT_META = OrderedDict([
        ("p", {"label": "Porción", "short": "P"}),
        ("p5", {"label": "5 porciones", "short": "5P"}),
        ("pq", {"label": "Pequeño 8-10", "short": "Pq"}),
        ("gr", {"label": "Grande 12-16", "short": "Gr"}),
        ("xg", {"label": "25-30 porciones", "short": "25-30"}),
        ("xg40", {"label": "40 porciones", "short": "40P"}),
        ("pl40_45", {"label": "40-45 porciones", "short": "40-45"}),
        ("pl55_60", {"label": "55-60 porciones", "short": "55-60"}),
        ("pl100", {"label": "100 porciones", "short": "100"}),
        ("other", {"label": "Otra", "short": "Otra"}),
    ])

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            vals["name"] = self.env["ir.sequence"].next_by_code("pasteleria.pos.daily.report") or "Nuevo"
        return super().create(vals)

    def action_regenerate_report(self):
        for report in self:
            try:
                report._generate_report_data()
                report._generate_excel_file()
                report._generate_pdf_file()

                report.state = "generated"

            except Exception as e:
                report.state = "error"
                report.summary_text = (report.summary_text or "") + _("\nERROR al regenerar reporte: %s") % str(e)
                raise

    def action_download_excel(self):
        self.ensure_one()
        if not self.excel_file:
            raise ValidationError(_("Este reporte aún no tiene archivo Excel generado."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/excel_file/{self.excel_filename}?download=true",
            "target": "self",
        }
    

    def action_download_pdf(self):
        self.ensure_one()
        if not self.pdf_file:
            raise ValidationError(_("Este reporte aún no tiene archivo PDF generado."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true",
            "target": "self",
        }

    # =========================================================
    # GENERACIÓN DE DATOS
    # =========================================================

    def _generate_report_data(self):
        self.ensure_one()
        self.line_ids.unlink()

        if not self.session_id.start_at or not self.session_id.stop_at:
            raise ValidationError(_("La sesión no tiene rango de fechas válido para generar el reporte."))

        product_maps = self.env["pasteleria.pos.report.product.map"].search([
            ("include_in_report", "=", True),
            ("available_in_pos", "=", True),
            ("active", "=", True),
        ], order="category_name, family_name, variant_normalized, product_id")

        if not product_maps:
            raise ValidationError(_("No hay productos en el mapa del reporte. Actualiza el mapa desde productos POS."))

        grouped = self._group_maps_by_category_family(product_maps)
        payload = self._build_payload(grouped)

        total_amount_q = payload["total_amount_q"]
        summary_lines = [f"{cat['category_name']}: Q{cat['category_total']:,.2f}" for cat in payload["categories"]]

        line_commands = []
        sequence = 10

        for cat in payload["categories"]:
            line_commands.append((0, 0, {
                "sequence": sequence,
                "line_type": "category",
                "category_name": cat["category_name"],
                "display_name": cat["category_name"],
            }))
            sequence += 10

            for fam in cat["families"]:
                summary = self._build_odoo_summary_from_family_payload(fam)

                line_commands.append((0, 0, {
                    "sequence": sequence,
                    "line_type": "family",
                    "category_name": cat["category_name"],
                    "display_name": fam["family_name"],
                    **summary,
                }))
                sequence += 10

            line_commands.append((0, 0, {
                "sequence": sequence,
                "line_type": "subtotal",
                "category_name": cat["category_name"],
                "display_name": f"Subtotal {cat['category_name']}",
                "sales_amount_q": cat["category_total"],
            }))
            sequence += 10

        self.write({
            "line_ids": line_commands,
            "total_amount_q": total_amount_q,
            "summary_text": self._build_summary_text(total_amount_q, summary_lines),
            "report_payload": json.dumps(payload, ensure_ascii=False),
        })

    def _group_maps_by_category_family(self, product_maps):
        grouped = OrderedDict()
        for rec in product_maps:
            category = rec.category_name or "Sin categoría"
            family = rec.family_name or rec.product_display_name or rec.product_id.display_name

            if category not in grouped:
                grouped[category] = OrderedDict()
            if family not in grouped[category]:
                grouped[category][family] = self.env["pasteleria.pos.report.product.map"]

            grouped[category][family] |= rec

        return grouped

    def _build_payload(self, grouped):
        self.ensure_one()
        payload = {
            "session_id": self.session_id.id,
            "report_date": str(self.report_date or ""),
            "categories": [],
            "total_amount_q": 0.0,
        }

        for category_name, family_dict in grouped.items():
            category_used_variants = set()
            category_total = 0.0
            families_payload = []

            for family_name, maps in family_dict.items():
                family_payload = self._compute_family_payload(family_name, maps)
                families_payload.append(family_payload)
                category_total += family_payload["sales_amount_q"]
                category_used_variants.update(family_payload["used_variants"])

            ordered_variants = [code for code in self.VARIANT_META.keys() if code in category_used_variants]

            payload["categories"].append({
                "category_name": category_name,
                "variants": ordered_variants,
                "families": families_payload,
                "category_total": category_total,
            })
            payload["total_amount_q"] += category_total

        return payload

    def _compute_family_payload(self, family_name, maps):
        self.ensure_one()

        start_dt = self.session_id.start_at
        end_dt = self.session_id.stop_at

        variants = OrderedDict()
        sales_amount_q = 0.0
        used_variants = set()

        for rec in maps:
            product = rec.product_id
            variant = rec.variant_normalized or "other"
            if variant not in self.VARIANT_META:
                variant = "other"

            exist_qty = self._get_stock_qty_at_datetime(product, start_dt)
            income_qty = self._get_income_qty_for_session(product, start_dt, end_dt)
            expense_qty = self._get_outgoing_qty_for_session(product, start_dt, end_dt)
            waste_qty = self._get_waste_qty_for_session(product, start_dt, end_dt)
            sales_qty, sales_amount = self._get_sales_qty_amount_for_session(product)
            final_qty = self._get_stock_qty_at_datetime(product, end_dt)

            if variant not in variants:
                variants[variant] = {
                    "exist": 0.0,
                    "income": 0.0,
                    "expense": 0.0,
                    "waste": 0.0,
                    "sales": 0.0,
                    "final": 0.0,
                }

            variants[variant]["exist"] += exist_qty
            variants[variant]["income"] += income_qty
            variants[variant]["expense"] += expense_qty
            variants[variant]["waste"] += waste_qty
            variants[variant]["sales"] += sales_qty
            variants[variant]["final"] += final_qty

            sales_amount_q += sales_amount
            used_variants.add(variant)

        return {
            "family_name": family_name,
            "variants": variants,
            "used_variants": list(used_variants),
            "sales_amount_q": sales_amount_q,
        }

    def _build_odoo_summary_from_family_payload(self, family_payload):
        variants = family_payload["variants"]

        def getv(code, key):
            return variants.get(code, {}).get(key, 0.0)

        # Enteros / completos
        whole_codes = ["pq", "gr", "xg", "xg40", "pl40_45", "pl55_60", "pl100"]
        # Porciones / piezas / otros
        portion_codes = ["p", "other"]

        exist_e = sum(getv(code, "exist") for code in whole_codes)
        income_e = sum(getv(code, "income") for code in whole_codes)
        expense_e = sum(getv(code, "expense") for code in whole_codes)
        waste_e = sum(getv(code, "waste") for code in whole_codes)
        sales_e = sum(getv(code, "sales") for code in whole_codes)
        final_e = sum(getv(code, "final") for code in whole_codes)

        exist_p = sum(getv(code, "exist") for code in portion_codes)
        income_p = sum(getv(code, "income") for code in portion_codes)
        expense_p = sum(getv(code, "expense") for code in portion_codes)
        waste_p = sum(getv(code, "waste") for code in portion_codes)
        sales_p = sum(getv(code, "sales") for code in portion_codes)
        final_p = sum(getv(code, "final") for code in portion_codes)

        exist_pq = getv("pq", "exist")
        exist_gr = getv("gr", "exist")
        income_pq = getv("pq", "income")
        income_gr = getv("gr", "income")
        expense_pq = getv("pq", "expense")
        expense_gr = getv("gr", "expense")
        waste_pq = getv("pq", "waste")
        waste_gr = getv("gr", "waste")
        sales_pq = getv("pq", "sales")
        sales_gr = getv("gr", "sales")
        final_pq = getv("pq", "final")
        final_gr = getv("gr", "final")

        return {
            "exist_e": exist_e,
            "exist_pq": exist_pq,
            "exist_gr": exist_gr,
            "exist_p": exist_p,

            "income_e": income_e,
            "income_pq": income_pq,
            "income_gr": income_gr,
            "income_p": income_p,

            "expense_e": expense_e,
            "expense_pq": expense_pq,
            "expense_gr": expense_gr,
            "expense_p": expense_p,

            "waste_e": waste_e,
            "waste_pq": waste_pq,
            "waste_gr": waste_gr,
            "waste_p": waste_p,

            "sales_e": sales_e,
            "sales_pq": sales_pq,
            "sales_gr": sales_gr,
            "sales_p": sales_p,

            "sales_amount_q": family_payload["sales_amount_q"],

            "final_e": final_e,
            "final_pq": final_pq,
            "final_gr": final_gr,
            "final_p": final_p,
        }

    def _build_summary_text(self, total_amount_q, summary_lines):
        text = _("Reporte generado correctamente.\n")
        text += _("Total general: Q%(amount).2f\n\n") % {"amount": total_amount_q}
        if summary_lines:
            text += _("Totales por categoría:\n")
            text += "\n".join(summary_lines)
        return text

    # =========================================================
    # CÁLCULOS
    # =========================================================

    def _get_report_location(self):
        self.ensure_one()
        warehouse = self.session_id.config_id.picking_type_id.warehouse_id
        return warehouse.lot_stock_id if warehouse and warehouse.lot_stock_id else False

    def _get_stock_qty_at_datetime(self, product, dt_value):
        if not product or not dt_value:
            return 0.0

        location = self._get_report_location()
        if not location:
            return 0.0

        qty = product.with_context(
            to_date=dt_value,
            location=location.id,
        ).qty_available

        return qty or 0.0

    def _get_income_qty_for_session(self, product, start_dt, end_dt):
        if not product:
            return 0.0

        location_dest = self._get_report_location()
        if not location_dest:
            return 0.0

        moves = self.env["stock.move"].search([
            ("product_id", "=", product.id),
            ("state", "=", "done"),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            ("location_dest_id", "child_of", location_dest.id),
        ])
        return sum(moves.mapped("product_uom_qty"))

    def _get_outgoing_qty_for_session(self, product, start_dt, end_dt):
        if not product:
            return 0.0

        source_location = self._get_report_location()
        if not source_location or "pasteleria.pos.transfer" not in self.env:
            return 0.0

        transfers = self.env["pasteleria.pos.transfer"].search([
            ("state", "=", "confirmed"),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            ("source_location_id", "child_of", source_location.id),
        ])

        qty = 0.0
        for transfer in transfers:
            for line in transfer.line_ids.filtered(lambda l: l.product_id.id == product.id):
                qty += line.qty
        return qty

    def _get_waste_qty_for_session(self, product, start_dt, end_dt):
        if not product or "pasteleria.desecho" not in self.env:
            return 0.0

        source_location = self._get_report_location()
        if not source_location:
            return 0.0

        deseho_model = self.env["pasteleria.desecho"]
        desechos = deseho_model.search([
            ("state", "=", "confirmed"),
            ("location_id", "child_of", source_location.id),
        ])

        qty = 0.0
        for desecho in desechos:
            effective_dt = desecho.approved_date or desecho.requested_date
            if effective_dt and start_dt <= effective_dt <= end_dt:
                for line in desecho.line_ids.filtered(lambda l: l.product_id.id == product.id):
                    qty += line.qty
        return qty

    def _get_sales_qty_amount_for_session(self, product):
        if not product:
            return 0.0, 0.0

        lines = self.env["pos.order.line"].search([
            ("order_id.session_id", "=", self.session_id.id),
            ("product_id", "=", product.id),
            ("order_id.state", "in", ["paid", "done", "invoiced"]),
        ])

        qty = sum(lines.mapped("qty"))
        amount = sum(lines.mapped("price_subtotal_incl"))
        return qty, amount

    # =========================================================
    # EXCEL / PDF
    # =========================================================

    def _generate_excel_file(self):
        self.ensure_one()

        if not self.report_payload:
            raise ValidationError(_("Este reporte aún no tiene payload calculado. Regenera el reporte primero."))

        payload = json.loads(self.report_payload)

        output = io.BytesIO()
        workbook = None

        try:
            import xlsxwriter

            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet("Reporte Final Día")

            fmt_title = workbook.add_format({
                "bold": True,
                "font_size": 14,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_header_group = workbook.add_format({
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#D9EAD3",
            })
            fmt_header_sub = workbook.add_format({
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#EADFD3",
            })
            fmt_cell = workbook.add_format({
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_text = workbook.add_format({
                "border": 1,
                "valign": "vcenter",
            })
            fmt_category = workbook.add_format({
                "bold": True,
                "border": 1,
                "bg_color": "#F4CCCC",
            })
            fmt_subtotal = workbook.add_format({
                "bold": True,
                "border": 1,
                "bg_color": "#FFF2CC",
            })
            fmt_total = workbook.add_format({
                "bold": True,
                "border": 1,
                "align": "center",
                "bg_color": "#D9D2E9",
            })

            sheet.set_column("A:A", 30)
            sheet.set_column("B:ZZ", 10)

            row = 0
            sheet.merge_range(row, 0, row, 40, "PASTELERÍA - REPORTE FINAL DEL DÍA", fmt_title)
            row += 2

            sheet.write(row, 0, "Sesión", fmt_header_group)
            sheet.write(row, 1, self.session_id.name or "", fmt_cell)
            sheet.write(row, 2, "POS", fmt_header_group)
            sheet.write(row, 3, self.config_id.display_name or "", fmt_cell)
            sheet.write(row, 4, "Fecha", fmt_header_group)
            sheet.write(row, 5, str(self.report_date or ""), fmt_cell)
            row += 2

            operation_groups = [
                ("Existencia", "exist"),
                ("Ingresos", "income"),
                ("Egresos", "expense"),
                ("Desechos", "waste"),
                ("Ventas del día", "sales"),
                ("Saldo final", "final"),
            ]

            for category in payload["categories"]:
                variants = category["variants"] or []

                if not variants:
                    continue

                total_columns = 1 + (len(operation_groups) * len(variants)) + 1

                sheet.merge_range(row, 0, row, total_columns - 1, category["category_name"], fmt_category)
                row += 1

                # Encabezado fila 1: grupos de operación
                sheet.merge_range(row, 0, row + 1, 0, "Descripción", fmt_header_group)
                col = 1

                for label, _key in operation_groups:
                    start_col = col
                    end_col = col + len(variants) - 1
                    sheet.merge_range(row, start_col, row, end_col, label, fmt_header_group)
                    col = end_col + 1

                sheet.merge_range(row, col, row + 1, col, "VTA-Q", fmt_header_group)

                # Encabezado fila 2: variantes
                sub_col = 1
                for _label, _key in operation_groups:
                    for var_code in variants:
                        meta = self.VARIANT_META.get(var_code, {"short": var_code})
                        sheet.write(row + 1, sub_col, meta["short"], fmt_header_sub)
                        sub_col += 1

                row += 2

                for family in category["families"]:
                    sheet.write(row, 0, family["family_name"], fmt_text)
                    col = 1

                    for _label, key in operation_groups:
                        for var_code in variants:
                            values = family["variants"].get(var_code, {})
                            sheet.write(row, col, values.get(key, 0.0), fmt_cell)
                            col += 1

                    sheet.write(row, col, family["sales_amount_q"], fmt_cell)
                    row += 1

                sheet.write(row, 0, f"Subtotal {category['category_name']}", fmt_subtotal)
                for c in range(1, total_columns - 1):
                    sheet.write(row, c, "", fmt_subtotal)
                sheet.write(row, total_columns - 1, category["category_total"], fmt_subtotal)
                row += 2

            sheet.merge_range(row, 0, row, 3, "TOTAL GENERAL Q", fmt_total)
            sheet.write(row, 4, payload["total_amount_q"], fmt_total)

            workbook.close()
            output.seek(0)

            filename = f"reporte_final_dia_{self.session_id.id}.xlsx"
            self.write({
                "excel_file": base64.b64encode(output.read()),
                "excel_filename": filename,
            })

        finally:
            if workbook:
                try:
                    workbook.close()
                except Exception:
                    pass
            output.close()
    def _generate_pdf_file(self):
        self.ensure_one()

        report_action = self.env["ir.actions.report"].sudo().search([
            ("model", "=", "pasteleria.pos.daily.report"),
            ("report_type", "=", "qweb-pdf"),
            ("report_name", "=", "pasteleria_pos_reporte_cierre_dia.report_daily_report_pdf"),
            ("report_file", "=", "pasteleria_pos_reporte_cierre_dia.report_daily_report_pdf"),
        ], order="id desc", limit=1)

        if not report_action:
            raise ValidationError(_("No se encontró una acción válida del reporte PDF."))

        pdf_content, _content_type = report_action._render_qweb_pdf(
            report_action.report_name,
            res_ids=[self.id],
        )

        filename = f"reporte_final_dia_{self.session_id.id}.pdf"

        self.write({
            "pdf_file": base64.b64encode(pdf_content),
            "pdf_filename": filename,
        })
        return True