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

    def _coerce_opening_amount(self, amount):
        if amount in (False, None, ""):
            return 0.0
        if isinstance(amount, (int, float)):
            return float(amount)
        if isinstance(amount, str):
            return float(amount.strip() or 0.0)
        if isinstance(amount, dict):
            for key in ("amount", "opening_amount", "balance", "value", "cashbox_value"):
                if key in amount:
                    return self._coerce_opening_amount(amount[key])
        raise ValidationError(_("No se pudo interpretar el monto de apertura enviado por el POS."))

    def _validate_exact_opening_amount(self, opening_amount):
        self.ensure_one()

        if not self._must_validate_exact_opening():
            return

        expected_amount = self._get_expected_opening_amount()
        precision = self.currency_id.rounding if self.currency_id else 0.01

        is_equal = float_compare(
            opening_amount,
            expected_amount,
            precision_rounding=precision,
        ) == 0

        if not is_equal:
            raise ValidationError(
                _(
                    "La caja no puede abrirse porque el monto contado (%(counted).2f) "
                    "no coincide exactamente con el monto esperado (%(expected).2f)."
                ) % {
                    "counted": opening_amount,
                    "expected": expected_amount,
                }
            )

    def _set_opening_control_data(self, cashbox_value, notes):
        """
        Odoo 18 abre la sesión por aquí.
        Validamos primero y luego dejamos seguir al flujo nativo.
        """
        for session in self:
            opening_amount = session._coerce_opening_amount(cashbox_value)
            session._validate_exact_opening_amount(opening_amount)

        return super()._set_opening_control_data(cashbox_value, notes)