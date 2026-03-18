# -*- coding: utf-8 -*-
import base64
import io
from collections import defaultdict

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
    currency_id = fields.Many2one("res.currency", string="Moneda", default=lambda self: self.env.company.currency_id.id, required=True)
    state = fields.Selection([("draft", "Borrador"), ("generated", "Generado"), ("error", "Error")], default="draft", required=True)
    line_ids = fields.One2many("pasteleria.pos.daily.report.line", "report_id", string="Líneas")
    excel_file = fields.Binary(string="Archivo Excel", attachment=True)
    excel_filename = fields.Char(string="Nombre Excel")
    pdf_file = fields.Binary(string="Archivo PDF", attachment=True)
    pdf_filename = fields.Char(string="Nombre PDF")
    summary_text = fields.Text(string="Resumen")

    _sql_constraints = [(
        "unique_session_report",
        "unique(session_id)",
        "Ya existe un reporte final del día para esta sesión POS.",
    )]

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            vals["name"] = self.env["ir.sequence"].next_by_code("pasteleria.pos.daily.report") or "Nuevo"
        return super().create(vals)

    def action_regenerate_report(self):
        self.ensure_one()
        self._generate_full_report()

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

    def _generate_full_report(self):
        self.ensure_one()
        self._generate_report_data()
        self._generate_excel_file()

        pdf_error = False
        try:
            self._generate_pdf_file()
        except Exception as e:
            pdf_error = str(e)

        if pdf_error:
            self.summary_text = (self.summary_text or "") + _("\nPDF no generado: %s") % pdf_error

        self.state = "generated"

    def _generate_report_data(self):
        self.ensure_one()
        self.line_ids.unlink()

        session = self.session_id
        if not session.start_at or not session.stop_at:
            raise ValidationError(_("La sesión no tiene rango de fechas válido para generar el reporte."))

        product_maps = self.env["pasteleria.pos.report.product.map"].search([
            ("include_in_report", "=", True),
            ("available_in_pos", "=", True),
            ("active", "=", True),
        ], order="category_name, family_name, variant_normalized, product_id")
        if not product_maps:
            raise ValidationError(_("No hay productos mapeados para el reporte. Reconstruye el mapa desde productos POS."))

        grouped = defaultdict(lambda: defaultdict(lambda: {"pq": self.env["product.product"], "gr": self.env["product.product"], "p": self.env["product.product"], "other": self.env["product.product"]}))
        for item in product_maps:
            category = item.category_name or _("Sin categoría")
            family = item.family_name or item.product_tmpl_id.name or item.product_display_name
            grouped[category][family][item.variant_normalized] |= item.product_id

        total_amount_q = 0.0
        line_vals_list = []
        sequence = 10

        for category_name in sorted(grouped.keys()):
            line_vals_list.append((0, 0, {
                "sequence": sequence,
                "line_type": "section",
                "category_name": category_name,
                "display_name": category_name,
            }))
            sequence += 10

            for family_name in sorted(grouped[category_name].keys()):
                bucket = grouped[category_name][family_name]
                values = self._compute_family_values(bucket)
                total_amount_q += values["sales_amount_q"]
                line_vals_list.append((0, 0, {
                    "sequence": sequence,
                    "line_type": "data",
                    "category_name": category_name,
                    "display_name": family_name,
                    **values,
                }))
                sequence += 10

        self.write({
            "line_ids": line_vals_list,
            "total_amount_q": total_amount_q,
            "summary_text": self._build_summary_text_preview(line_vals_list, total_amount_q),
        })

    def _build_summary_text_preview(self, line_vals_list, total_amount_q):
        data_lines = [v for v in line_vals_list if v[2].get("line_type") == "data"]
        total_lines = len(data_lines)
        total_qty = sum(v[2].get("sales_e", 0.0) + v[2].get("sales_p", 0.0) for v in data_lines)
        categories = len({v[2].get("category_name") for v in data_lines})
        return _(
            "Reporte generado con %(categories)s categorías, %(lines)s filas de producto. Total unidades vendidas: %(qty)s. Total Q: %(amount)s"
        ) % {
            "categories": categories,
            "lines": total_lines,
            "qty": total_qty,
            "amount": total_amount_q,
        }

    def _compute_family_values(self, bucket):
        session = self.session_id
        start_dt = session.start_at
        end_dt = session.stop_at

        products_pq = bucket.get("pq", self.env["product.product"])
        products_gr = bucket.get("gr", self.env["product.product"])
        products_p = bucket.get("p", self.env["product.product"])

        exist_pq = self._get_stock_qty_at_datetime(products_pq, start_dt)
        exist_gr = self._get_stock_qty_at_datetime(products_gr, start_dt)
        exist_p = self._get_stock_qty_at_datetime(products_p, start_dt)

        final_pq = self._get_stock_qty_at_datetime(products_pq, end_dt)
        final_gr = self._get_stock_qty_at_datetime(products_gr, end_dt)
        final_p = self._get_stock_qty_at_datetime(products_p, end_dt)

        income_pq = self._get_income_qty_for_session(products_pq, start_dt, end_dt)
        income_gr = self._get_income_qty_for_session(products_gr, start_dt, end_dt)
        income_p = self._get_income_qty_for_session(products_p, start_dt, end_dt)

        sales_pq, amount_pq = self._get_sales_qty_amount_for_session(products_pq)
        sales_gr, amount_gr = self._get_sales_qty_amount_for_session(products_gr)
        sales_p, amount_p = self._get_sales_qty_amount_for_session(products_p)

        return {
            "exist_e": exist_pq + exist_gr,
            "exist_pq": exist_pq,
            "exist_gr": exist_gr,
            "exist_p": exist_p,
            "income_e": income_pq + income_gr,
            "income_pq": income_pq,
            "income_gr": income_gr,
            "income_p": income_p,
            "sales_e": sales_pq + sales_gr,
            "sales_pq": sales_pq,
            "sales_gr": sales_gr,
            "sales_p": sales_p,
            "sales_amount_q": amount_pq + amount_gr + amount_p,
            "final_e": final_pq + final_gr,
            "final_pq": final_pq,
            "final_gr": final_gr,
            "final_p": final_p,
        }

    def _get_pos_stock_location(self):
        self.ensure_one()
        warehouse = self.session_id.config_id.picking_type_id.warehouse_id
        return warehouse.lot_stock_id if warehouse and warehouse.lot_stock_id else False

    def _get_stock_qty_at_datetime(self, products, dt_value):
        if not products or not dt_value:
            return 0.0
        location = self._get_pos_stock_location()
        if not location:
            return 0.0
        qty = 0.0
        for product in products:
            qty += product.with_context(to_date=dt_value, location=location.id).qty_available or 0.0
        return qty

    def _get_income_qty_for_session(self, products, start_dt, end_dt):
        if not products:
            return 0.0
        location_dest = self._get_pos_stock_location()
        if not location_dest:
            return 0.0
        moves = self.env["stock.move"].search([
            ("product_id", "in", products.ids),
            ("state", "=", "done"),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            ("location_dest_id", "child_of", location_dest.id),
        ])
        return sum(moves.mapped("product_uom_qty"))

    def _get_sales_qty_amount_for_session(self, products):
        if not products:
            return 0.0, 0.0
        lines = self.env["pos.order.line"].search([
            ("order_id.session_id", "=", self.session_id.id),
            ("product_id", "in", products.ids),
            ("order_id.state", "in", ["paid", "done", "invoiced"]),
        ])
        qty = sum(lines.mapped("qty"))
        amount = sum(lines.mapped("price_subtotal_incl"))
        return qty, amount

    def _generate_excel_file(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = None
        try:
            import xlsxwriter
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet("Reporte Final Día")

            fmt_title = workbook.add_format({"bold": True, "font_size": 14, "align": "center"})
            fmt_header = workbook.add_format({"bold": True, "border": 1, "align": "center", "valign": "vcenter", "bg_color": "#D9E2F3"})
            fmt_cell = workbook.add_format({"border": 1, "align": "center"})
            fmt_text = workbook.add_format({"border": 1})
            fmt_section = workbook.add_format({"bold": True, "border": 1, "bg_color": "#F4CCCC"})
            fmt_total = workbook.add_format({"bold": True, "border": 1, "align": "center", "bg_color": "#FFF2CC"})

            sheet.set_column("A:A", 30)
            sheet.set_column("B:R", 10)

            row = 0
            sheet.merge_range(row, 0, row, 17, "PASTELERÍA - REPORTE FINAL DEL DÍA", fmt_title)
            row += 2

            sheet.write(row, 0, "Sesión", fmt_header)
            sheet.write(row, 1, self.session_id.name or "", fmt_cell)
            sheet.write(row, 2, "POS", fmt_header)
            sheet.write(row, 3, self.config_id.display_name or "", fmt_cell)
            sheet.write(row, 4, "Fecha", fmt_header)
            sheet.write(row, 5, str(self.report_date or ""), fmt_cell)
            row += 2

            headers = [
                "Descripción",
                "Exist. E", "Exist. Pq", "Exist. Gr", "Exist. P",
                "Ing. E", "Ing. Pq", "Ing. Gr", "Ing. P",
                "Venta E", "Venta Pq", "Venta Gr", "Venta P",
                "VTA-Q",
                "Saldo E", "Saldo Pq", "Saldo Gr", "Saldo P",
            ]
            for col, header in enumerate(headers):
                sheet.write(row, col, header, fmt_header)
            row += 1

            current_category = None
            category_start_row = None
            category_total_q = 0.0

            for line in self.line_ids.sorted("sequence"):
                if line.line_type == "section":
                    if current_category is not None:
                        sheet.merge_range(row, 0, row, 12, f"Subtotal {current_category}", fmt_total)
                        sheet.write(row, 13, category_total_q, fmt_total)
                        for col in range(14, 18):
                            sheet.write(row, col, "", fmt_total)
                        row += 1

                    current_category = line.display_name
                    category_total_q = 0.0
                    category_start_row = row
                    sheet.merge_range(row, 0, row, 17, current_category, fmt_section)
                    row += 1
                    continue

                category_total_q += line.sales_amount_q
                sheet.write(row, 0, line.display_name or "", fmt_text)
                sheet.write(row, 1, line.exist_e, fmt_cell)
                sheet.write(row, 2, line.exist_pq, fmt_cell)
                sheet.write(row, 3, line.exist_gr, fmt_cell)
                sheet.write(row, 4, line.exist_p, fmt_cell)
                sheet.write(row, 5, line.income_e, fmt_cell)
                sheet.write(row, 6, line.income_pq, fmt_cell)
                sheet.write(row, 7, line.income_gr, fmt_cell)
                sheet.write(row, 8, line.income_p, fmt_cell)
                sheet.write(row, 9, line.sales_e, fmt_cell)
                sheet.write(row, 10, line.sales_pq, fmt_cell)
                sheet.write(row, 11, line.sales_gr, fmt_cell)
                sheet.write(row, 12, line.sales_p, fmt_cell)
                sheet.write(row, 13, line.sales_amount_q, fmt_cell)
                sheet.write(row, 14, line.final_e, fmt_cell)
                sheet.write(row, 15, line.final_pq, fmt_cell)
                sheet.write(row, 16, line.final_gr, fmt_cell)
                sheet.write(row, 17, line.final_p, fmt_cell)
                row += 1

            if current_category is not None:
                sheet.merge_range(row, 0, row, 12, f"Subtotal {current_category}", fmt_total)
                sheet.write(row, 13, category_total_q, fmt_total)
                for col in range(14, 18):
                    sheet.write(row, col, "", fmt_total)
                row += 1

            sheet.merge_range(row, 0, row, 12, "TOTAL Q", fmt_total)
            sheet.write(row, 13, self.total_amount_q, fmt_total)
            for col in range(14, 18):
                sheet.write(row, col, "", fmt_total)

            workbook.close()
            output.seek(0)
            self.write({
                "excel_file": base64.b64encode(output.read()),
                "excel_filename": f"reporte_final_dia_{self.session_id.id}.xlsx",
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
        report_action = self.env.ref("pasteleria_pos_reporte_cierre_dia.action_report_daily_report_pdf", raise_if_not_found=False)
        if not report_action:
            return False
        pdf_content, _content_type = report_action._render_qweb_pdf(self.id)
        self.write({
            "pdf_file": base64.b64encode(pdf_content),
            "pdf_filename": f"reporte_final_dia_{self.session_id.id}.pdf",
        })
        return True
