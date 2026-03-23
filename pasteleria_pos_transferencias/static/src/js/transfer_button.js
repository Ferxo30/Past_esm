/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onMounted, onWillUnmount } from "@odoo/owl";

console.log("[Pasteleria Transferencias] transfer_button.js cargado ✅");

function getOrm(ctx) {
    return ctx.env?.services?.orm || ctx.orm || null;
}

function getPosConfigId(ctx) {
    return ctx.pos?.config?.id || ctx.env?.pos?.config?.id || null;
}

async function openTransfersBackend(ctx) {
    const orm = getOrm(ctx);
    const posConfigId = getPosConfigId(ctx);

    if (!orm) {
        console.error("[Pasteleria Transferencias] ORM no disponible");
        window.alert("No se pudo abrir Transferencias.");
        return;
    }

    try {
        const result = await orm.call(
            "pasteleria.pos.transfer",
            "get_pos_transfer_backend_url",
            [posConfigId]
        );

        if (!result?.url) {
            window.alert("No se pudo construir la URL de Transferencias.");
            return;
        }

        window.open(result.url, "_blank");
    } catch (error) {
        console.error("[Pasteleria Transferencias] Error abriendo backend:", error);
        const message =
            error?.data?.message ||
            error?.message ||
            "No se pudo abrir la vista de Transferencias.";
        window.alert(message);
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
    item.className = "list-group-item dropdown-item";
    item.style.width = "100%";
    item.style.textAlign = "left";
    item.textContent = "Transferencias";

    item.addEventListener("click", async () => {
        console.log("[Pasteleria Transferencias] click menú transferencias");
        await openTransfersBackend(ctx);
    });

    container.appendChild(item);
    console.log("[Pasteleria Transferencias] item insertado en menú hamburguesa ✅");
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