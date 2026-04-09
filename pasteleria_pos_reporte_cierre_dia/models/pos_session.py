# -*- coding: utf-8 -*-
from odoo import fields, models, _


class PosSession(models.Model):
    _inherit = "pos.session"

    daily_report_id = fields.Many2one(
        "pasteleria.pos.daily.report",
        string="Reporte final del día",
        readonly=True,
        copy=False,
    )

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super().action_pos_session_closing_control(
            balancing_account=balancing_account,
            amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs,
        )
        for session in self:
            if session.state == "closed":
                session._create_or_update_daily_report()
        return res

    def _create_or_update_daily_report(self):
        Report = self.env["pasteleria.pos.daily.report"]
        Map = self.env["pasteleria.pos.report.product.map"]

        if not Map.search_count([]):
            Map.action_rebuild_from_pos_products()

        for session in self:
            report = Report.search([("session_id", "=", session.id)], limit=1)
            vals = {
                "session_id": session.id,
                "user_id": self.env.user.id,
                "report_date": session.stop_at.date() if session.stop_at else False,
                "date_open": session.start_at,
                "date_close": session.stop_at,
            }
            if report:
                report.write(vals)
            else:
                report = Report.create(vals)

            try:
                report._generate_report_data()
                report._generate_excel_file()
                report._generate_pdf_file()
                report.state = "generated"
            except Exception as e:
                report.state = "error"
                report.summary_text = (report.summary_text or "") + _("\nError generando reporte automático: %s") % str(e)

            session.daily_report_id = report.id