import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    @api.model
    def _pos_today(self):
        return fields.Date.context_today(self)

    def _normalize_expiration_to_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        return fields.Datetime.to_datetime(value)

    def _to_user_local_date(self, value):
        """
        Convierte un datetime del lote a fecha local del usuario/POS.
        Esto evita errores por UTC vs hora local.
        """
        dt = self._normalize_expiration_to_datetime(value)
        if not dt:
            return False
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.date()

    def _get_effective_expiration_value(self, lot):
        candidates = [
            ("expiration_date", getattr(lot, "expiration_date", False)),
            ("life_date", getattr(lot, "life_date", False)),
            ("use_date", getattr(lot, "use_date", False)),
            ("removal_date", getattr(lot, "removal_date", False)),
            ("alert_date", getattr(lot, "alert_date", False)),
        ]

        for preferred in ["expiration_date", "life_date", "use_date", "removal_date", "alert_date"]:
            for field_name, raw_value in candidates:
                if field_name == preferred and raw_value:
                    return {
                        "field": field_name,
                        "raw": raw_value,
                        "datetime": self._normalize_expiration_to_datetime(raw_value),
                        "local_date": self._to_user_local_date(raw_value),
                    }

        return {
            "field": False,
            "raw": False,
            "datetime": False,
            "local_date": False,
        }

    @api.model
    def _compute_expiry_state(self, lot, today=None, warning_days=2):
        """
        Semáforo por FECHA LOCAL, no por hora.
        Negro   = ayer o antes
        Rojo    = hoy
        Amarillo= mañana o pasado mañana
        Verde   = 3 días o más
        """
        today = today or self._pos_today()
        expiry_info = self._get_effective_expiration_value(lot)
        expiration_date = expiry_info["local_date"]

        if not expiration_date:
            return "green", False, False, 999999

        if expiration_date < today:
            return "black", False, True, -1

        delta = (expiration_date - today).days
        if delta == 0:
            return "red", True, False, 0
        if delta <= warning_days:
            return "yellow", True, False, delta
        return "green", True, False, delta

    @api.model
    def _get_pos_source_location(self, pos_config):
        location = getattr(pos_config, "transfer_source_location_id", False) or pos_config.picking_type_id.default_location_src_id
        if not location:
            raise UserError(_("No se encontró la ubicación origen del POS '%s'.") % pos_config.display_name)
        return location

    @api.model
    def _get_qty_by_lot(self, location, product_ids):
        Quant = self.env["stock.quant"].sudo()
        domain = [
            ("location_id", "child_of", location.id),
            ("product_id", "in", product_ids),
            ("lot_id", "!=", False),
            ("quantity", ">", 0),
        ]
        grouped = Quant.read_group(
            domain,
            ["product_id", "lot_id", "quantity:sum", "reserved_quantity:sum"],
            ["product_id", "lot_id"],
            lazy=False,
        )
        result = {}
        for row in grouped:
            qty = (row.get("quantity") or 0.0) - (row.get("reserved_quantity") or 0.0)
            if qty <= 0:
                continue
            product_id = row["product_id"][0]
            lot_id = row["lot_id"][0]
            result[(product_id, lot_id)] = qty
        return result

    @api.model
    def pos_build_product_expiry_snapshot(self, pos_config_id, product_ids):
        if not pos_config_id:
            raise UserError(_("Se requiere pos_config_id para calcular semáforos de lotes."))

        pos_config = self.env["pos.config"].browse(pos_config_id).exists()
        if not pos_config:
            raise UserError(_("No se encontró la configuración del POS."))

        product_ids = product_ids or []
        if not product_ids:
            return {"products": {}, "templates": {}}

        location = self._get_pos_source_location(pos_config)
        qty_by_lot = self._get_qty_by_lot(location, product_ids)
        lot_ids = [lot_id for (_, lot_id), qty in qty_by_lot.items() if qty > 0]
        lots = self.browse(list(set(lot_ids))).sudo()

        lots_by_product = defaultdict(list)
        lot_index = {lot.id: lot for lot in lots}
        products = self.env["product.product"].browse(product_ids).sudo()
        warning_days_by_product = {
            p.id: (getattr(p, "x_pos_expiry_warning_days", 2) or 2)
            for p in products
        }

        for (product_id, lot_id), qty in qty_by_lot.items():
            lot = lot_index.get(lot_id)
            if not lot:
                continue

            warning_days = warning_days_by_product.get(product_id, 2)
            state, sellable, expired, days_left = self._compute_expiry_state(
                lot,
                today=self._pos_today(),
                warning_days=warning_days,
            )

            expiry_info = self._get_effective_expiration_value(lot)
            expiration_date = expiry_info["local_date"]

            lots_by_product[product_id].append({
                "lot_id": lot.id,
                "lot_name": lot.name,
                "expiration_date": fields.Date.to_string(expiration_date) if expiration_date else False,
                "expiry_field": expiry_info["field"],
                "state": state,
                "sellable": sellable,
                "expired": expired,
                "days_left": days_left,
                "qty_available": qty,
            })

        priority = {"red": 0, "yellow": 1, "green": 2, "black": 3}

        product_snapshot = {}
        template_bucket = defaultdict(list)

        for product in products:
            product_lots = lots_by_product.get(product.id, [])
            sellable_lots = [lot for lot in product_lots if lot["sellable"]]
            expired_lots = [lot for lot in product_lots if lot["expired"]]

            preferred_lot = None
            if sellable_lots:
                preferred_lot = sorted(
                    sellable_lots,
                    key=lambda x: (
                        priority.get(x["state"], 9),
                        x["days_left"],
                        x["lot_name"],
                    ),
                )[0]

            summary_state = None
            if sellable_lots:
                summary_state = sorted(
                    sellable_lots,
                    key=lambda x: (priority[x["state"]], x["days_left"], x["lot_name"])
                )[0]["state"]
            elif expired_lots:
                summary_state = "black"

            record = {
                "product_id": product.id,
                "product_name": product.display_name,
                "template_id": product.product_tmpl_id.id,
                "summary_state": summary_state,
                "has_expired_lots": bool(expired_lots),
                "has_sellable_lots": bool(sellable_lots),
                "preferred_lot_id": preferred_lot["lot_id"] if preferred_lot else False,
                "preferred_lot_name": preferred_lot["lot_name"] if preferred_lot else False,
                "lots": sorted(
                    product_lots,
                    key=lambda x: (
                        priority.get(x["state"], 9),
                        x["days_left"],
                        x["lot_name"],
                    ),
                ),
            }
            product_snapshot[product.id] = record
            template_bucket[product.product_tmpl_id.id].append(record)

        template_snapshot = {}
        for template_id, records in template_bucket.items():
            candidate_lots = []
            has_expired_lots = False
            has_sellable_lots = False

            for rec in records:
                has_expired_lots = has_expired_lots or rec["has_expired_lots"]
                has_sellable_lots = has_sellable_lots or rec["has_sellable_lots"]
                for lot in rec.get("lots", []):
                    candidate_lots.append(lot)

            summary_state = None
            if candidate_lots:
                candidate_lots = sorted(
                    candidate_lots,
                    key=lambda x: (
                        {"red": 0, "yellow": 1, "green": 2, "black": 3}.get(x.get("state"), 9),
                        x.get("days_left", 999999),
                        x.get("lot_name", ""),
                    ),
                )
                summary_state = candidate_lots[0].get("state")

            template_snapshot[template_id] = {
                "template_id": template_id,
                "template_name": records[0]["product_name"].split(" (")[0] if records and records[0].get("product_name") else False,
                "summary_state": summary_state,
                "has_expired_lots": has_expired_lots,
                "has_sellable_lots": has_sellable_lots,
            }

        return {
            "products": product_snapshot,
            "templates": template_snapshot,
        }

    @api.model
    def pos_validate_sellable_lots(self, pos_config_id, lot_ids):
        """
        Bloqueo de venta por FECHA LOCAL:
        - si caduca ayer o antes: bloquea
        - si caduca hoy: permite
        """
        pos_config = self.env["pos.config"].browse(pos_config_id).exists()
        if not pos_config:
            raise UserError(_("No se encontró el POS para validar lotes."))

        today = self._pos_today()
        invalid = []

        for lot in self.browse(lot_ids).sudo().exists():
            expiry_info = self._get_effective_expiration_value(lot)
            expiration_date = expiry_info["local_date"]

            if expiration_date and expiration_date < today:
                invalid.append({
                    "lot_id": lot.id,
                    "lot_name": lot.name,
                    "product_name": lot.product_id.display_name,
                    "expiration_date": fields.Date.to_string(expiration_date),
                    "expiry_field": expiry_info["field"],
                })

        return invalid

    @api.model
    def pos_validate_sellable_lots_from_payload(self, pos_config_id, lot_payload):
        """
        Bloqueo de venta por FECHA LOCAL:
        - negro = ayer o antes => no vender
        - rojo = hoy => sí vender
        """
        pos_config = self.env["pos.config"].browse(pos_config_id).exists()
        if not pos_config:
            raise UserError(_("No se encontró el POS para validar lotes."))

        today = self._pos_today()
        invalid = []
        StockLot = self.sudo()

        _logger.warning(
            "[POS LOT EXPIRY] Validando desde payload. POS=%s payload=%s today=%s",
            pos_config.display_name,
            lot_payload,
            today,
        )

        seen = set()

        for item in lot_payload or []:
            product_id = item.get("product_id")
            lot_name = item.get("lot_name")

            if not lot_name or not product_id:
                continue

            lot = StockLot.search([
                ("name", "=", lot_name),
                ("product_id", "=", product_id),
            ], limit=1)

            if not lot:
                continue

            if lot.id in seen:
                continue
            seen.add(lot.id)

            expiry_info = self._get_effective_expiration_value(lot)
            expiration_date = expiry_info["local_date"]

            _logger.warning(
                "[POS LOT EXPIRY] Payload resuelto a lote: id=%s name=%s product=%s "
                "expiration_date=%s life_date=%s use_date=%s removal_date=%s alert_date=%s "
                "effective_field=%s effective_local_date=%s",
                lot.id,
                lot.name,
                lot.product_id.display_name,
                getattr(lot, "expiration_date", False),
                getattr(lot, "life_date", False),
                getattr(lot, "use_date", False),
                getattr(lot, "removal_date", False),
                getattr(lot, "alert_date", False),
                expiry_info["field"],
                expiration_date,
            )

            if expiration_date and expiration_date < today:
                invalid.append({
                    "lot_id": lot.id,
                    "lot_name": lot.name,
                    "product_name": lot.product_id.display_name,
                    "expiration_date": fields.Date.to_string(expiration_date),
                    "expiry_field": expiry_info["field"],
                })

        _logger.warning("[POS LOT EXPIRY] Resultado payload inválidos=%s", invalid)
        return invalid