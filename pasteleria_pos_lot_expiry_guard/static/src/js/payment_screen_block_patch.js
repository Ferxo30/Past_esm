/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

console.log("[POS LOT EXPIRY] payment_screen_block_patch.js cargado ✅");

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        console.log("[POS LOT EXPIRY] validateOrder() interceptado");

        const invalid = await this.pos.validateCurrentOrderLotsForSale();
        console.log("[POS LOT EXPIRY] invalid lots =>", invalid);

        if (invalid.length) {
            const first = invalid[0];
            this.dialog.add(AlertDialog, {
                title: _t("Lote vencido"),
                body: _t(
                    "No se puede continuar al pago porque el lote '%s' del producto '%s' está vencido desde %s."
                )
                    .replace("%s", first.lot_name)
                    .replace("%s", first.product_name)
                    .replace("%s", first.expiration_date_label || first.expiration_date),
            });
            return;
        }

        return await super.validateOrder(isForceValidate);
    },
});