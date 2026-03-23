/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class CakeFractionPopup extends Component {
    static template = "pasteleria_pos_fraccionamiento.CakeFractionPopup";
    static components = { Dialog };
    static props = ["close", "product"];

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            qty_full: 1,
            qty_slices_created: 0,
            note: "",
            reason_id: "",
            reasons: [],
            slice_product_id: false,
            slice_product_name: "",
        });

        onWillStart(async () => {
            await this.loadReasons();
            this.loadSliceProduct();
        });
    }

    get fullProduct() {
        return this.props.product;
    }

    _normalizeId(value) {
        if (!value) return false;

        if (typeof value === "number") {
            return value;
        }

        if (typeof value === "string" && !isNaN(Number(value))) {
            return Number(value);
        }

        if (Array.isArray(value) && value.length) {
            return this._normalizeId(value[0]);
        }

        if (typeof value === "object") {
            if ("id" in value && value.id) {
                return this._normalizeId(value.id);
            }
            if ("resId" in value && value.resId) {
                return this._normalizeId(value.resId);
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
            if (normalized) {
                return normalized;
            }
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

    loadSliceProduct() {
        const product = this.fullProduct;
        this.state.slice_product_id = this._normalizeId(product?.cake_slice_product_id) || false;

        const dbProducts = this.pos?.db?.product_by_id || {};
        const sliceProduct = this.state.slice_product_id
            ? dbProducts[this.state.slice_product_id]
            : null;

        this.state.slice_product_name = sliceProduct?.display_name || "No configurado";
    }

    async confirm() {
        const qtyFull = Number(this.state.qty_full || 0);
        const qtySlices = Number(this.state.qty_slices_created || 0);
        const reasonId = this.state.reason_id ? Number(this.state.reason_id) : false;
        const posSessionId = this.getPosSessionId();

        if (!posSessionId) {
            this.notification.add(
                _t("No se pudo identificar la sesión POS activa."),
                { type: "danger" }
            );
            console.error("[Pasteleria Fraccionamiento] posSessionId no encontrado", this.pos);
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

        const payload = {
            pos_session_id: posSessionId,
            full_product_id: this._normalizeId(this.fullProduct.id),
            qty_full: qtyFull,
            qty_slices_created: qtySlices,
            reason_id: reasonId || false,
            note: this.state.note || "",
        };

        console.log("[Pasteleria Fraccionamiento] Payload:", payload);

        try {
            const result = await this.orm.call(
                "pasteleria.cake.fraction",
                "create_fraction_from_pos",
                [payload]
            );

            this.notification.add(
                _t("Fraccionamiento registrado: %s", result.name),
                { type: "success" }
            );

            this.props.close();
        } catch (error) {
            console.error("[Pasteleria Fraccionamiento] Error creando fraccionamiento:", error);
            const message =
                error?.data?.message ||
                error?.message ||
                "No se pudo registrar el fraccionamiento.";
            this.notification.add(message, { type: "danger" });
        }
    }
}