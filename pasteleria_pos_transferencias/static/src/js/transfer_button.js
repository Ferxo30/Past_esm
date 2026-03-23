/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { TransferPopup } from "./transfer_popup";

console.log("[Pasteleria Transferencias] transfer_button.js cargado ✅");

function getOrm(ctx) {
    return ctx.env?.services?.orm || ctx.orm || null;
}

function getDialog(ctx) {
    return ctx.env?.services?.dialog || null;
}

function getPosConfigId(ctx) {
    return ctx.pos?.config?.id || ctx.env?.pos?.config?.id || null;
}

async function openTransfersPopup(ctx) {
    const orm = getOrm(ctx);
    const dialog = getDialog(ctx);
    const posConfigId = getPosConfigId(ctx);

    if (!orm || !dialog || !posConfigId) {
        window.alert("No se pudo abrir Transferencias.");
        return;
    }

    try {
        const data = await orm.call(
            "pasteleria.pos.transfer",
            "pos_get_transfer_popup_data",
            [posConfigId]
        );

        dialog.add(TransferPopup, {
            originPosId: data.origin_pos_id,
            originPosName: data.origin_pos_name,
            destinations: data.destinations,
            products: data.products,
        });
    } catch (error) {
        console.error("[Pasteleria Transferencias] Error cargando popup:", error);
        window.alert(
            error?.data?.message || error?.message || "No se pudo abrir el popup de Transferencias."
        );
    }
}

function getHamburgerPopupContainer() {
    const selectors = [
        ".popover .list-group",
        ".dropdown-menu",
        ".menu .list-group",
        ".pos .popover",
    ];

    for (const selector of selectors) {
        const node = document.querySelector(selector);
        if (node) {
            return node;
        }
    }

    return null;
}

function insertTransferMenuItem(ctx) {
    if (document.getElementById("btn_pos_transfer_menu")) {
        return true;
    }

    const container = getHamburgerPopupContainer();
    if (!container) {
        return false;
    }

    const item = document.createElement("button");
    item.id = "btn_pos_transfer_menu";
    item.type = "button";
    item.className = "dropdown-item o_pos_transfer_menu_item";
    item.innerHTML = `
        <div class="o_pos_transfer_menu_inner">
            <span class="o_pos_transfer_menu_label">Transferencias</span>
        </div>
    `;

    item.addEventListener("click", async () => {
        await openTransfersPopup(ctx);
    });

    container.appendChild(item);
    return true;
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            let tries = 0;
            const timer = setInterval(() => {
                tries += 1;
                const menuOpen = document.querySelector(".dropdown-menu, .popover, .menu");
                if (menuOpen) {
                    insertTransferMenuItem(this);
                }
                if (tries >= 80) {
                    clearInterval(timer);
                }
            }, 500);
            this.__pasteleria_transfer_timer__ = timer;
        });

        onWillUnmount(() => {
            if (this.__pasteleria_transfer_timer__) {
                clearInterval(this.__pasteleria_transfer_timer__);
                this.__pasteleria_transfer_timer__ = null;
            }
        });
    },
});