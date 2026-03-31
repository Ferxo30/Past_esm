from odoo import api, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    @api.model
    def get_existing_lots(self, company_id, product_id):
        lots = super().get_existing_lots(company_id, product_id)

        lot_ids = [lot["id"] for lot in lots if lot.get("id")]
        if not lot_ids:
            return lots

        lot_records = self.env["stock.lot"].sudo().browse(lot_ids).exists()
        expiry_by_id = {}
        for lot in lot_records:
            expiry_info = lot._get_effective_expiration_value(lot)
            expiration_date = expiry_info["local_date"]

            state, sellable, expired, days_left = lot._compute_expiry_state(
                lot,
                today=lot._pos_today(),
                warning_days=(getattr(lot.product_id, "x_pos_expiry_warning_days", 2) or 2),
            )

            expiry_by_id[lot.id] = {
                "expiry_field": expiry_info["field"],
                "expiration_date": expiration_date and expiration_date.isoformat() or False,
                "state": state,
                "sellable": sellable,
                "expired": expired,
                "days_left": days_left,
            }

        result = []
        for item in lots:
            extra = expiry_by_id.get(item["id"], {})
            merged = dict(item)
            merged.update(extra)
            result.append(merged)

        priority = {"red": 0, "yellow": 1, "green": 2, "black": 3}
        result.sort(
            key=lambda x: (
                priority.get(x.get("state", "green"), 9),
                x.get("days_left", 999999),
                x.get("name", ""),
            )
        )
        return result