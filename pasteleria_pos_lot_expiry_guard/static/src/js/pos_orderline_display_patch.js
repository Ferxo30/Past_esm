/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

console.log("[POS LOT EXPIRY] pos_orderline_display_patch.js cargado ✅");

patch(PosOrderline.prototype, {
    getDisplayData() {
        const data = super.getDisplayData(...arguments);

        const productId = this.product_id?.id || false;
        const templateId = this.product_id?.product_tmpl_id?.id || this.product_id?.product_tmpl_id || false;

        let expiryInfo = null;
        try {
            expiryInfo = this.models?.["pos.session"]?.[0]?.pos?.getProductExpiryInfo?.(productId, templateId) || null;
        } catch (err) {
            console.warn("[POS LOT EXPIRY] No se pudo resolver expiryInfo desde getDisplayData()", err);
        }

        return {
            ...data,
            productId,
            templateId,
            expiryInfo,
        };
    },
});