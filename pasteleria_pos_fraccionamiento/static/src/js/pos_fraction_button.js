/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { CakeFractionPopup } from "./fraction_popup";

console.log("[Pasteleria Fraccionamiento] pos_fraction_button.js cargado ✅");

function getOrder(ctx) {
    return ctx.pos?.get_order?.() || ctx.currentOrder || ctx.env?.pos?.get_order?.() || null;
}

function getSelectedOrderLine(order) {
    if (!order) return null;
    if (typeof order.get_selected_orderline === "function") {
        return order.get_selected_orderline();
    }
    return null;
}

function getProductFromLine(line) {
    if (!line) return null;
    if (line.product) return line.product;
    if (typeof line.get_product === "function") {
        try {
            return line.get_product();
        } catch (_) {}
    }
    return null;
}

function getProductTemplateId(product) {
    const value = product?.product_tmpl_id;
    if (!value) return false;
    if (typeof value === "number") return value;
    if (Array.isArray(value) && value.length) return value[0];
    if (typeof value === "object" && value.id) return value.id;
    return false;
}

function resolveSliceProductId(product, pos) {
    const direct = product?.cake_slice_product_id;
    if (typeof direct === "number") return direct;
    if (Array.isArray(direct) && direct.length) return direct[0];
    if (typeof direct === "object" && direct?.id) return direct.id;

    const templateId = getProductTemplateId(product);
    if (!templateId) return false;

    const records = pos?.models?.["product.product"]?.getAll?.() || [];
    const found = records.find((p) => {
        const tmpl = getProductTemplateId(p);
        return tmpl === templateId && !!p?.is_cake_slice;
    });
    return found?.id || false;
}

function findPayButtonElement() {
    const nodes = Array.from(document.querySelectorAll("button,div,span,a"));
    const byText = nodes.find((n) => (n.textContent || "").trim() === "Pago");
    return byText ? byText.closest("button") || byText : null;
}

function ensureFractionButton(ctx) {
    if (document.getElementById("btn_pasteleria_fraction")) {
        return true;
    }

    const payEl = findPayButtonElement();
    if (!payEl || !payEl.parentElement) return false;

    const btn = document.createElement("button");
    btn.id = "btn_pasteleria_fraction";
    btn.type = "button";
    btn.textContent = "Fraccionar";
    btn.className = "pasteleria_fraction_trigger_btn";
    btn.style.marginBottom = "6px";
    btn.style.padding = "12px 10px";
    btn.style.border = "1px solid #875A7B";
    btn.style.borderRadius = "4px";
    btn.style.background = "#fff";
    btn.style.color = "#875A7B";
    btn.style.fontWeight = "600";
    btn.style.cursor = "pointer";

    btn.addEventListener("click", () => ctx.onClickCakeFraction());
    payEl.parentElement.insertBefore(btn, payEl);
    return true;
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            let tries = 0;
            const timer = setInterval(() => {
                tries += 1;
                const ok = ensureFractionButton(this);
                if (ok || tries >= 30) {
                    clearInterval(timer);
                }
            }, 200);
            this.__pasteleria_fraction_timer__ = timer;
        });

        onWillUnmount(() => {
            if (this.__pasteleria_fraction_timer__) {
                clearInterval(this.__pasteleria_fraction_timer__);
                this.__pasteleria_fraction_timer__ = null;
            }
        });
    },

    async onClickCakeFraction() {
        const order = getOrder(this);
        const line = getSelectedOrderLine(order);

        if (!line) {
            window.alert("Selecciona primero una línea con el pastel completo que quieres fraccionar.");
            return;
        }

        const product = getProductFromLine(line);
        if (!product || !product.can_be_fraction_source) {
            window.alert("La línea seleccionada no corresponde a un pastel completo fraccionable.");
            return;
        }

        const sliceProductId = resolveSliceProductId(product, this.pos);
        if (!sliceProductId) {
            window.alert("La variante seleccionada no tiene producto porción configurado.");
            return;
        }

        const dialog = this.env?.services?.dialog || this.dialog;
        if (!dialog) {
            console.error("[Pasteleria Fraccionamiento] No se encontró servicio dialog");
            window.alert("No se pudo abrir el popup de fraccionamiento.");
            return;
        }

        dialog.add(CakeFractionPopup, {
            product,
            orderline: line,
        });
    },
});