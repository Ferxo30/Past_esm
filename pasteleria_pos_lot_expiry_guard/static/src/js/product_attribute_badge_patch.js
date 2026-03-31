/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import {
    BaseProductAttribute,
} from "@point_of_sale/app/store/product_configurator_popup/product_configurator_popup";

console.log("[POS LOT EXPIRY] product_attribute_badge_patch.js cargado ✅");

function summarizeLots(lots) {
    if (!lots.length) {
        return null;
    }

    const priority = { red: 0, yellow: 1, green: 2, black: 3 };
    const sorted = [...lots].sort((a, b) => {
        const pa = priority[a.state] ?? 99;
        const pb = priority[b.state] ?? 99;
        if (pa !== pb) return pa - pb;

        const da = a.days_left ?? 999999;
        const db = b.days_left ?? 999999;
        if (da !== db) return da - db;

        return String(a.lot_name || "").localeCompare(String(b.lot_name || ""));
    });

    return {
        summary_state: sorted[0].state,
        has_expired_lots: lots.some((l) => !!l.expired),
    };
}

patch(BaseProductAttribute.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
    },

    getValueExpiryInfo(value) {
        const snapshot = window.__posLotExpirySnapshot || { products: {}, templates: {} };
        const snapshotProducts = Object.values(snapshot.products || []);

        // EXACTAMENTE el mismo criterio que usa Odoo base para resolver variantes:
        // product.raw.product_template_variant_value_ids
        const matchingProducts = this.pos.models["product.product"]
            .filter((p) => p.raw?.product_template_variant_value_ids?.includes(value.id));

        const matchingIds = new Set(matchingProducts.map((p) => p.id));

        const candidateLots = [];
        for (const product of snapshotProducts) {
            if (matchingIds.has(product.product_id)) {
                for (const lot of product.lots || []) {
                    candidateLots.push(lot);
                }
            }
        }

        const info = summarizeLots(candidateLots);

        console.log("[POS LOT EXPIRY] attribute value expiry info", {
            valueId: value.id,
            valueName: value.name,
            matchingProductIds: [...matchingIds],
            info,
        });

        return info;
    },
});