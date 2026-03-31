/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";

function normalizeName(value) {
    return String(value || "")
        .replace(/\u00A0/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
}

function baseName(value) {
    const text = String(value || "").trim();
    return text.split(" (")[0].trim();
}

function buildCatalogSummaryByName(snapshot, visibleName) {
    const products = Object.values(snapshot?.products || {});
    const target = normalizeName(baseName(visibleName));
    if (!target) {
        return null;
    }

    const priority = { red: 0, yellow: 1, green: 2, black: 3 };
    const candidateLots = [];

    for (const product of products) {
        const productBase = normalizeName(baseName(product.product_name));
        if (productBase === target) {
            for (const lot of product.lots || []) {
                candidateLots.push(lot);
            }
        }
    }

    if (!candidateLots.length) {
        return null;
    }

    candidateLots.sort((a, b) => {
        const pa = priority[a.state] ?? 99;
        const pb = priority[b.state] ?? 99;
        if (pa !== pb) return pa - pb;

        const da = a.days_left ?? 999999;
        const db = b.days_left ?? 999999;
        if (da !== db) return da - db;

        return String(a.lot_name || "").localeCompare(String(b.lot_name || ""));
    });

    const summary_state = candidateLots[0]?.state || null;
    const has_expired_lots = candidateLots.some((lot) => !!lot.expired);

    return {
        summary_state,
        has_expired_lots,
        has_sellable_lots: candidateLots.some((lot) => !!lot.sellable),
    };
}

patch(ProductCard.prototype, {
    get expiryIndicatorState() {
        if (!this.env?.services?.pos) {
            return null;
        }

        const rawProduct =
            this.props?.product ||
            this.props?.item ||
            null;

        const visibleName =
            this.props?.name ||
            rawProduct?.display_name ||
            rawProduct?.name ||
            rawProduct?.raw?.display_name ||
            rawProduct?.raw?.name ||
            null;

        const snapshot = window.__posLotExpirySnapshot || { products: {}, templates: {} };
        const info = buildCatalogSummaryByName(snapshot, visibleName);

        console.log("[POS LOT EXPIRY] product card expiry info", {
            visibleName,
            info,
        });

        return info;
    },
});