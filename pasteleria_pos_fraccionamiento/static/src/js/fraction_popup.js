/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STATE_LABELS = {
    green: "Verde",
    yellow: "Amarillo",
    red: "Rojo",
    black: "Negro",
};

export class CakeFractionPopup extends Component {
    static template = "pasteleria_pos_fraccionamiento.CakeFractionPopup";
    static components = { Dialog };
    static props = ["close", "product", "orderline"];

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.selectLot = this.selectLot.bind(this);
        this.confirm = this.confirm.bind(this);

        this.state = useState({
            qty_full: 1,
            qty_slices_created: 0,
            note: "",
            reason_id: "",
            reasons: [],
            slice_product_id: false,
            slice_product_name: "",
            source_lot_id: "",
            available_lots: [],
            loading_lots: true,
        });

        onWillStart(async () => {
            await this.loadReasons();
            await this.loadSliceProduct();
            await this.loadLots();
        });
    }

    get fullProduct() {
        return this.props.product;
    }

    _normalizeId(value) {
        if (!value) return false;
        if (typeof value === "number") return value;
        if (typeof value === "string" && !isNaN(Number(value))) return Number(value);
        if (Array.isArray(value) && value.length) return this._normalizeId(value[0]);
        if (typeof value === "object") {
            if ("id" in value && value.id) return this._normalizeId(value.id);
            if ("resId" in value && value.resId) return this._normalizeId(value.resId);
        }
        return false;
    }

    _getTemplateId(product) {
        return this._normalizeId(product?.product_tmpl_id);
    }

    _findSliceProductFromPos() {
        const templateId = this._getTemplateId(this.fullProduct);
        const productRecords = this.pos?.models?.["product.product"]?.getAll?.() || [];

        const byTemplate = productRecords.find((p) => {
            const tmplId = this._normalizeId(p?.product_tmpl_id);
            return tmplId === templateId && !!p?.is_cake_slice;
        });
        if (byTemplate) {
            return byTemplate;
        }

        const dbProducts = this.pos?.db?.product_by_id || {};
        return Object.values(dbProducts).find((p) => {
            const tmplId = this._normalizeId(p?.product_tmpl_id);
            return tmplId === templateId && !!p?.is_cake_slice;
        }) || null;
    }

    _getSelectedOrderlineLotId() {
        const lineLots = this.props.orderline?.pack_lot_ids || [];
        for (const lotLine of lineLots) {
            const id = this._normalizeId(lotLine?.id || lotLine?.lot_id);
            if (id) {
                return id;
            }
        }
        return false;
    }

    getPosSessionId() {
        const candidates = [
            this.pos?.pos_session?.id,
            this.pos?.pos_session,
            this.pos?.pos_session_id,
            this.pos?.config?.current_session_id,
            this.pos?.config_id?.current_session_id,
            this.pos?.session?.id,
            this.pos?.session,
        ];

        for (const candidate of candidates) {
            const normalized = this._normalizeId(candidate);
            if (normalized) return normalized;
        }
        return false;
    }

    async loadReasons() {
        try {
            this.state.reasons = await this.orm.searchRead(
                "pasteleria.cake.fraction.reason",
                [["active", "=", true]],
                ["name"]
            );
        } catch (error) {
            console.error("[Pasteleria Fraccionamiento] Error cargando motivos:", error);
            this.state.reasons = [];
        }
    }

    async loadSliceProduct() {
        const currentProduct = this.fullProduct;

        let sliceProductId = this._normalizeId(currentProduct?.cake_slice_product_id) || false;
        let sliceProductName = "";

        const foundInPos = this._findSliceProductFromPos();
        if (!sliceProductId && foundInPos) {
            sliceProductId = this._normalizeId(foundInPos.id);
        }
        if (foundInPos?.display_name) {
            sliceProductName = foundInPos.display_name;
        }

        const dbProducts = this.pos?.db?.product_by_id || {};
        const sliceFromDb = sliceProductId ? dbProducts[sliceProductId] : null;
        if (sliceFromDb?.display_name) {
            sliceProductName = sliceFromDb.display_name;
        }

        if (!sliceProductId || !sliceProductName) {
            try {
                const records = await this.orm.read(
                    "product.product",
                    [this._normalizeId(currentProduct?.id)],
                    ["cake_slice_product_id"]
                );
                const fullRecord = records?.[0] || null;
                const backendSlice = fullRecord?.cake_slice_product_id || false;
                const backendSliceId = this._normalizeId(backendSlice);
                if (backendSliceId) {
                    sliceProductId = backendSliceId;
                    if (Array.isArray(backendSlice) && backendSlice[1]) {
                        sliceProductName = backendSlice[1];
                    }
                }
            } catch (error) {
                console.warn("[Pasteleria Fraccionamiento] No se pudo leer cake_slice_product_id por ORM:", error);
            }
        }

        if (sliceProductId && !sliceProductName) {
            try {
                const sliceRecords = await this.orm.read(
                    "product.product",
                    [sliceProductId],
                    ["display_name"]
                );
                sliceProductName = sliceRecords?.[0]?.display_name || "";
            } catch (error) {
                console.warn("[Pasteleria Fraccionamiento] No se pudo leer display_name de la porción:", error);
            }
        }

        this.state.slice_product_id = sliceProductId || false;
        this.state.slice_product_name = sliceProductName || "No configurado";
    }

    getLotStateLabel(state) {
        return STATE_LABELS[state] || state || "";
    }

    getLotCssClass(state) {
        return `o_fraction_lot_badge o_fraction_lot_badge_${state || "green"}`;
    }

    selectLot(lotIdText) {
        this.state.source_lot_id = lotIdText ? String(lotIdText) : "";
    }

    async loadLots() {
        this.state.loading_lots = true;
        try {
            const snapshot = await this.orm.call(
                "product.product",
                "pos_get_expiry_snapshot",
                [this.pos.config.id, [this._normalizeId(this.fullProduct.id)]]
            );

            const productInfo = snapshot?.products?.[this._normalizeId(this.fullProduct.id)] || null;
            const lots = (productInfo?.lots || []).map((lot) => ({
                ...lot,
                lot_id_text: String(lot.lot_id),
                selectable: !!lot.sellable,
                label: `${lot.lot_name} - ${this.getLotStateLabel(lot.state)} - Disp: ${lot.qty_available}${lot.expiration_date ? ` - Vence: ${lot.expiration_date}` : ""}`,
            }));

            this.state.available_lots = lots;

            const selectedOrderlineLotId = this._getSelectedOrderlineLotId();
            const preferredId = selectedOrderlineLotId || productInfo?.preferred_lot_id || false;
            const preferredLot = lots.find((lot) => lot.lot_id === preferredId && lot.selectable);
            const firstSelectable = lots.find((lot) => lot.selectable);

            this.state.source_lot_id = String(preferredLot?.lot_id || firstSelectable?.lot_id || "");
        } catch (error) {
            console.error("[Pasteleria Fraccionamiento] Error cargando lotes:", error);
            this.state.available_lots = [];
            this.state.source_lot_id = "";
        } finally {
            this.state.loading_lots = false;
        }
    }

    async confirm() {
        const qtyFull = Number(this.state.qty_full || 0);
        const qtySlices = Number(this.state.qty_slices_created || 0);
        const reasonId = this.state.reason_id ? Number(this.state.reason_id) : false;
        const posSessionId = this.getPosSessionId();
        const sourceLotId = this.state.source_lot_id ? Number(this.state.source_lot_id) : false;

        if (!posSessionId) {
            this.notification.add(_t("No se pudo identificar la sesión POS activa."), { type: "danger" });
            return;
        }
        if (qtyFull <= 0) {
            this.notification.add(_t("Debes indicar una cantidad válida de enteros."), { type: "danger" });
            return;
        }
        if (qtySlices <= 0) {
            this.notification.add(_t("Debes indicar una cantidad válida de porciones generadas."), { type: "danger" });
            return;
        }
        if (!this.state.slice_product_id) {
            this.notification.add(_t("Este pastel no tiene producto porción configurado."), { type: "danger" });
            return;
        }
        if (!sourceLotId) {
            this.notification.add(_t("Debes seleccionar un lote."), { type: "danger" });
            return;
        }

        const payload = {
            pos_session_id: posSessionId,
            full_product_id: this._normalizeId(this.fullProduct.id),
            source_lot_id: sourceLotId,
            qty_full: qtyFull,
            qty_slices_created: qtySlices,
            reason_id: reasonId || false,
            note: this.state.note || "",
        };

        try {
            const result = await this.orm.call("pasteleria.cake.fraction", "create_fraction_from_pos", [payload]);
            this.notification.add(`${_t("Fraccionamiento registrado")}: ${result.name}`, { type: "success" });
            this.props.close();
        } catch (error) {
            console.error("[Pasteleria Fraccionamiento] Error creando fraccionamiento:", error);
            const message = error?.data?.message || error?.message || "No se pudo registrar el fraccionamiento.";
            this.notification.add(message, { type: "danger" });
        }
    }
}