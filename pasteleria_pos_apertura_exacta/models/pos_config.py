from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    x_cash_opening_exact_enabled = fields.Boolean(
        string="Validar apertura exacta",
        default=True,
        help="Si está activo, el monto de apertura del POS debe coincidir exactamente con el monto esperado.",
    )
    x_cash_opening_expected_amount = fields.Monetary(
        string="Monto esperado de apertura",
        currency_field="currency_id",
        help="Monto exacto que la cajera debe registrar al abrir la caja.",
    )

    def _check_cash_opening_manager_permissions(self):
        if self.env.is_superuser():
            return
        allowed = (
            self.env.user.has_group("pasteleria_desechos.group_pasteleria_gerente")
            or self.env.user.has_group("pasteleria_desechos.group_pasteleria_admin")
        )
        if not allowed:
            raise ValidationError(
                _("Solo un gerente o administrador puede modificar la configuración de apertura de caja.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        restricted_fields = {
            "x_cash_opening_exact_enabled",
            "x_cash_opening_expected_amount",
        }
        for vals in vals_list:
            if restricted_fields.intersection(vals.keys()):
                self._check_cash_opening_manager_permissions()
                break
        return super().create(vals_list)

    def write(self, vals):
        restricted_fields = {
            "x_cash_opening_exact_enabled",
            "x_cash_opening_expected_amount",
        }
        if restricted_fields.intersection(vals.keys()):
            self._check_cash_opening_manager_permissions()
        return super().write(vals)
