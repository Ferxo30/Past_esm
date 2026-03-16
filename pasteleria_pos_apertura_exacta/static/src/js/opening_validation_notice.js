/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Este parche es deliberadamente liviano: solo intenta mostrar un texto de apoyo
// en el popup nativo sin tocar la lógica de sesión.
// Si Odoo cambia internamente este componente, la validación REAL sigue quedando
// protegida del lado servidor en set_cashbox_pos().

try {
    const module = await import("@point_of_sale/app/store/opening_popup/opening_control_popup");
    const OpeningControlPopup = module.OpeningControlPopup;

    if (OpeningControlPopup) {
        patch(OpeningControlPopup.prototype, {
            setup() {
                super.setup(...arguments);
                const config = this.pos?.config || {};
                this.expectedOpeningAmount = config.x_cash_opening_expected_amount || 0;
            },
            get openingExactValidationMessage() {
                const currencySymbol = this.pos?.currency?.symbol || "Q";
                if (!this.expectedOpeningAmount) {
                    return "";
                }
                return _t("Monto esperado: %s %s", currencySymbol, Number(this.expectedOpeningAmount).toFixed(2));
            },
        });
    }
} catch (_error) {
    // No rompemos el POS si cambia la ruta interna del popup.
    // La validación sigue activa en backend.
}
