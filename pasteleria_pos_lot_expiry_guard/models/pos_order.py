from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _extract_lot_candidates_from_ui_line(self, ui_line):
        results = []
        if not ui_line or len(ui_line) < 3:
            return results

        values = ui_line[2] or {}
        product_id = values.get("product_id")

        pack_lot_ids = (
            values.get("pack_lot_ids")
            or values.get("pack_lot_lines")
            or values.get("lot_lines")
            or []
        )

        for item in pack_lot_ids:
            payload = None

            if isinstance(item, dict):
                payload = item
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                payload = item[2] or {}

            if not payload:
                continue

            lot_id = payload.get("lot_id") or payload.get("id")
            lot_name = (
                payload.get("lot_name")
                or payload.get("name")
                or payload.get("text")
                or payload.get("lot_name_full")
            )

            results.append({
                "product_id": product_id,
                "lot_id": lot_id,
                "lot_name": lot_name,
                "raw": payload,
            })

        return results

    @api.model
    def _extract_lot_candidates_from_order_payload(self, order_payload):
        results = []
        data = (order_payload or {}).get("data", {})
        pos_config_id = data.get("config_id")
        lines = data.get("lines", [])

        for line in lines:
            results.extend(self._extract_lot_candidates_from_ui_line(line))

        return pos_config_id, results

    @api.model
    def _resolve_real_lots_from_candidates(self, candidates):
        StockLot = self.env["stock.lot"].sudo()
        real_lot_ids = set()

        for candidate in candidates:
            product_id = candidate.get("product_id")
            lot_id = candidate.get("lot_id")
            lot_name = candidate.get("lot_name")

            lot = False

            if lot_id:
                lot = StockLot.browse(lot_id).exists()

            if not lot and lot_name and product_id:
                lot = StockLot.search([
                    ("name", "=", lot_name),
                    ("product_id", "=", product_id),
                ], limit=1)

            if lot:
                real_lot_ids.add(lot.id)

        return list(real_lot_ids)

    @api.model
    def create_from_ui(self, orders, draft=False):
        for order in orders or []:
            pos_config_id, candidates = self._extract_lot_candidates_from_order_payload(order)
            real_lot_ids = self._resolve_real_lots_from_candidates(candidates)

            if not real_lot_ids:
                continue

            invalid = self.env["stock.lot"].pos_validate_sellable_lots(pos_config_id, real_lot_ids)
            if invalid:
                first = invalid[0]
                raise ValidationError(_(
                    "No se puede generar la venta porque el lote '%(lot)s' del producto '%(product)s' está vencido desde %(date)s."
                ) % {
                    "lot": first["lot_name"],
                    "product": first["product_name"],
                    "date": first["expiration_date"],
                })

        return super().create_from_ui(orders, draft=draft)