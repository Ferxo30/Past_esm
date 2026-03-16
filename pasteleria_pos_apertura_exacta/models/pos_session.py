from odoo import models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PosSession(models.Model):
    _inherit = "pos.session"

    def _get_expected_opening_amount(self):
        self.ensure_one()
        return self.config_id.x_cash_opening_expected_amount or 0.0

    def _must_validate_exact_opening(self):
        self.ensure_one()
        return bool(self.config_id.cash_control and self.config_id.x_cash_opening_exact_enabled)

    def _validate_exact_opening_amount(self, opening_amount):
        self.ensure_one()
        if not self._must_validate_exact_opening():
            return

        expected_amount = self._get_expected_opening_amount()
        precision = self.currency_id.rounding if self.currency_id else 0.01
        is_equal = float_compare(opening_amount, expected_amount, precision_rounding=precision) == 0
        if not is_equal:
            raise ValidationError(
                _(
                    "La caja no puede abrirse porque el monto contado (%(counted).2f) no coincide exactamente con el monto esperado (%(expected).2f)."
                )
                % {
                    "counted": opening_amount,
                    "expected": expected_amount,
                }
            )

    def _coerce_opening_amount(self, amount):
        """Convierte a float distintos formatos simples que pueda enviar el frontend."""
        if amount in (False, None, ""):
            return 0.0
        if isinstance(amount, (int, float)):
            return float(amount)
        if isinstance(amount, str):
            return float(amount.strip() or 0.0)
        if isinstance(amount, dict):
            # Compatibilidad defensiva si en algún flujo llegara un payload con varias llaves.
            for key in ("amount", "opening_amount", "balance", "value"):
                if key in amount:
                    return self._coerce_opening_amount(amount[key])
        raise ValidationError(_("No se pudo interpretar el monto de apertura enviado por el POS."))

    def set_cashbox_pos(self, amount, notes=None):
        """
        Hook nativo usado por el POS para confirmar el monto de apertura.
        Aquí solo validamos y luego dejamos que Odoo siga con su flujo normal.
        """
        for session in self:
            opening_amount = session._coerce_opening_amount(amount)
            session._validate_exact_opening_amount(opening_amount)
        return super().set_cashbox_pos(amount, notes=notes)
