/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

console.log("[Pasteleria Recargar Recibo] receipt_reload_button.js cargado ✅");

function getCurrentOrder(ctx) {
    return ctx.pos?.get_order?.() || ctx.currentOrder || ctx.props?.order || null;
}

function findNodeByExactText(text) {
    const nodes = Array.from(document.querySelectorAll("button, a, div, span"));
    return nodes.find((node) => (node.textContent || "").trim() === text) || null;
}

function getReceiptActionContainer() {
    const newOrderNode = findNodeByExactText("Nueva orden");
    if (newOrderNode) {
        const button = newOrderNode.closest("button") || newOrderNode;
        if (button?.parentElement) {
            return {
                mode: "before_new_order",
                target: button,
            };
        }
    }

    const printNode = findNodeByExactText("Imprimir recibo completo");
    if (printNode) {
        const button = printNode.closest("button") || printNode;
        if (button?.parentElement) {
            return {
                mode: "after_print",
                target: button,
            };
        }
    }

    const selectors = [
        ".receipt-screen .button.next.highlight",
        ".receipt-screen .default-view",
        ".receipt-screen .actions",
        ".receipt-screen .footer",
    ];

    for (const selector of selectors) {
        const node = document.querySelector(selector);
        if (node) {
            return {
                mode: "append",
                target: node,
            };
        }
    }

    return null;
}

function getOrCreateReloadStatusNode() {
    let node = document.getElementById("pos_receipt_reload_status");
    if (node) {
        return node;
    }

    const placement = getReceiptActionContainer();
    if (!placement?.target) {
        return null;
    }

    node = document.createElement("div");
    node.id = "pos_receipt_reload_status";
    node.className = "o_pos_receipt_reload_status";

    if (placement.mode === "before_new_order") {
        placement.target.parentElement.insertBefore(node, placement.target);
        return node;
    }

    if (placement.mode === "after_print") {
        placement.target.insertAdjacentElement("afterend", node);
        return node;
    }

    placement.target.appendChild(node);
    return node;
}

function updateReloadStatus(message, status = "info") {
    const node = getOrCreateReloadStatusNode();
    if (!node) {
        return;
    }

    node.className = `o_pos_receipt_reload_status o_status_${status}`;
    node.textContent = message;
}

function formatNow() {
    return new Date().toLocaleTimeString();
}

function setButtonTemporaryState(button, text, className = "") {
    if (!button) {
        return;
    }
    button.textContent = text;
    button.className = `button btn btn-secondary o_pos_reload_receipt_btn ${className}`.trim();
}

function insertReloadReceiptButton(ctx) {
    if (document.getElementById("btn_pos_reload_receipt")) {
        return true;
    }

    const placement = getReceiptActionContainer();
    if (!placement?.target) {
        return false;
    }

    const button = document.createElement("button");
    button.id = "btn_pos_reload_receipt";
    button.type = "button";
    button.className = "button btn btn-secondary o_pos_reload_receipt_btn";
    button.textContent = "Recargar recibo";

    button.addEventListener("click", async () => {
        await ctx.onClickReloadCurrentReceipt();
    });

    if (placement.mode === "before_new_order") {
        placement.target.parentElement.insertBefore(button, placement.target);
        return true;
    }

    if (placement.mode === "after_print") {
        placement.target.insertAdjacentElement("afterend", button);
        return true;
    }

    placement.target.appendChild(button);
    return true;
}

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.__pasteleria_receipt_reload_count__ = 0;

        onMounted(() => {
            let tries = 0;
            const timer = setInterval(() => {
                tries += 1;
                const okButton = insertReloadReceiptButton(this);
                const okStatus = !!getOrCreateReloadStatusNode();
                if ((okButton && okStatus) || tries >= 30) {
                    clearInterval(timer);
                }
            }, 250);
            this.__pasteleria_receipt_reload_timer__ = timer;
        });

        onWillUnmount(() => {
            if (this.__pasteleria_receipt_reload_timer__) {
                clearInterval(this.__pasteleria_receipt_reload_timer__);
                this.__pasteleria_receipt_reload_timer__ = null;
            }
        });
    },

    async onClickReloadCurrentReceipt() {
        const button = document.getElementById("btn_pos_reload_receipt");
        const order = getCurrentOrder(this);

        if (!order) {
            updateReloadStatus("No hay una orden actual para recargar.", "error");
            window.alert("No hay una orden actual para reconstruir el recibo.");
            return;
        }

        try {
            if (button) {
                button.disabled = true;
                setButtonTemporaryState(button, "Recargando...", "is_loading");
            }

            updateReloadStatus("Recargando recibo...", "info");

            // Fuerza el recálculo de los datos base del ticket.
            if (typeof order.export_for_printing === "function") {
                order.export_for_printing();
            }

            if (this.pos?.set_order) {
                this.pos.set_order(order);
            }

            if (typeof this.render === "function") {
                this.render(true);
                await new Promise((resolve) => window.setTimeout(resolve, 60));
                this.render(true);
            }

            this.__pasteleria_receipt_reload_count__ += 1;
            const successMessage = `Recibo recargado ${this.__pasteleria_receipt_reload_count__} vez/veces. Última recarga: ${formatNow()}`;
            updateReloadStatus(successMessage, "success");

            if (button) {
                setButtonTemporaryState(button, "Recargado ✓", "is_success");
                window.setTimeout(() => {
                    const refreshedButton = document.getElementById("btn_pos_reload_receipt");
                    if (refreshedButton) {
                        refreshedButton.disabled = false;
                        setButtonTemporaryState(refreshedButton, "Recargar recibo");
                        refreshedButton.blur();
                    }
                }, 1200);
            }
        } catch (error) {
            console.error("[Pasteleria Recargar Recibo] Error recargando recibo:", error);
            updateReloadStatus(
                `No se pudo recargar el recibo. ${error?.message || "Error desconocido."}`,
                "error"
            );
            if (button) {
                button.disabled = false;
                setButtonTemporaryState(button, "Reintentar recarga", "is_error");
            }
            window.alert(
                error?.message || "No se pudo reconstruir el recibo de la orden actual."
            );
        }
    },
});
