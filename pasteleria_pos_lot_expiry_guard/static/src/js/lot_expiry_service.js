/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

console.log("[POS LOT EXPIRY] lot_expiry_service.js cargado ✅");

function formatExpiryDate(expirationDate) {
    if (!expirationDate) {
        return "";
    }
    try {
        const d = new Date(expirationDate);
        return d.toLocaleString();
    } catch {
        return expirationDate;
    }
}

function normalizeLotName(value) {
    return String(value || "")
        .replace(/^lot number\s+/i, "")
        .replace(/\u00A0/g, " ")
        .trim();
}

function getGlobalSnapshot() {
    return window.__posLotExpirySnapshot || { products: {}, templates: {} };
}

function setGlobalSnapshot(snapshot) {
    window.__posLotExpirySnapshot = snapshot || { products: {}, templates: {} };
}

patch(PosStore.prototype, {
    async setup(...args) {
        await super.setup(...args);
        this.productExpirySnapshot = { products: {}, templates: {} };
        this.lotExpiryByProduct = {};
    },

    async processServerData(...args) {
        await super.processServerData(...args);
        await this.loadProductExpirySnapshot();
    },

    async loadProductExpirySnapshot(productIds = null) {
        let ids = productIds || [];

        if (!ids.length) {
            const productRecords = this.models?.["product.product"]?.getAll?.() || [];
            ids = productRecords.map((p) => p.id).filter((x) => !!x);
        }

        console.log("[POS LOT EXPIRY] product ids para snapshot =>", ids);

        if (!ids.length) {
            this.productExpirySnapshot = { products: {}, templates: {} };
            setGlobalSnapshot(this.productExpirySnapshot);
            console.warn("[POS LOT EXPIRY] No se encontraron product ids para cargar snapshot");
            return;
        }

        const snapshot = await this.data.call(
            "product.product",
            "pos_get_expiry_snapshot",
            [this.config.id, ids]
        );

        this.productExpirySnapshot = snapshot || { products: {}, templates: {} };
        setGlobalSnapshot(this.productExpirySnapshot);

        const products = Object.values(this.productExpirySnapshot?.products || {});
        const allLots = [];
        for (const product of products) {
            for (const lot of product.lots || []) {
                allLots.push({
                    lot_name: lot.lot_name,
                    state: lot.state,
                    product_name: product.product_name,
                });
            }
        }

        console.log("[POS LOT EXPIRY] snapshot =>", this.productExpirySnapshot);
        console.log("[POS LOT EXPIRY] snapshot products count =>", products.length);
        console.log("[POS LOT EXPIRY] snapshot lots =>", allLots);
    },

    getProductExpiryInfo(productId = false, templateId = false) {
        const snapshot = this.productExpirySnapshot?.products
            ? this.productExpirySnapshot
            : getGlobalSnapshot();

        const products = snapshot?.products || {};
        const templates = snapshot?.templates || {};

        // IMPORTANTE:
        // En catálogo queremos priorizar el template porque resume
        // el lote más próximo entre variantes.
        if (templateId && templates[templateId]) {
            return templates[templateId];
        }
        if (productId && products[productId]) {
            return products[productId];
        }
        return null;
    },

    getLotExpiryInfoByLotName(lotName) {
        if (!lotName) {
            return null;
        }

        const normalizedLotName = normalizeLotName(lotName);
        const localSnapshot = this.productExpirySnapshot?.products
            ? this.productExpirySnapshot
            : { products: {}, templates: {} };

        const globalSnapshot = getGlobalSnapshot();

        const localProducts = Object.values(localSnapshot?.products || {});
        const globalProducts = Object.values(globalSnapshot?.products || {});
        const products = globalProducts.length ? globalProducts : localProducts;

        let info = null;

        for (const product of products) {
            const found = (product.lots || []).find(
                (lot) => normalizeLotName(lot.lot_name) === normalizedLotName
            );
            if (found) {
                info = {
                    ...found,
                    product_id: product.product_id,
                    product_name: product.product_name,
                    summary_state: found.state,
                };
                break;
            }
        }

        console.log("[POS LOT EXPIRY] getLotExpiryInfoByLotName()", {
            lotName,
            normalizedLotName,
            info,
            localSnapshotProductsCount: localProducts.length,
            globalSnapshotProductsCount: globalProducts.length,
        });

        return info;
    },

    setLotExpiryMetadata(productId, lots) {
        this.lotExpiryByProduct[productId] = lots || [];
    },

    getLotExpiryMetadata(productId) {
        return this.lotExpiryByProduct?.[productId] || [];
    },

    async validateCurrentOrderLotsForSale() {
        const order = this.get_order();
        if (!order) {
            console.log("[POS LOT EXPIRY] No hay orden activa");
            return [];
        }

        const lotPayload = [];

        for (const line of order.get_orderlines()) {
            const product = line.get_product ? line.get_product() : line.product_id;
            const productId = product?.id || false;
            const packLots = line.pack_lot_ids || [];

            for (const lotLine of packLots) {
                lotPayload.push({
                    product_id: productId,
                    lot_id: lotLine.id || false,
                    lot_name: lotLine.lot_name || false,
                });
            }
        }

        if (!lotPayload.length) {
            return [];
        }

        const invalid = await this.data.call(
            "stock.lot",
            "pos_validate_sellable_lots_from_payload",
            [this.config.id, lotPayload]
        );

        return (invalid || []).map((item) => ({
            ...item,
            expiration_date_label: formatExpiryDate(item.expiration_date),
        }));
    },
});