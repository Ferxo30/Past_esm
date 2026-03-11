/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

console.log("[Pasteleria Desechos] desecho_manager_button.js cargado ✅");

function getOrm(ctx) {
    return ctx.env?.services?.orm || ctx.orm || null;
}

function openDesechoOrdersScreen(ctx) {
    const pos = ctx.pos || ctx.env?.services?.pos || ctx.env?.pos;
    if (pos && typeof pos.showScreen === "function") {
        pos.showScreen("DesechoOrdersScreen");
        return;
    }
    if (typeof ctx.showScreen === "function") {
        ctx.showScreen("DesechoOrdersScreen");
        return;
    }
    console.error("[Pasteleria Desechos] No se pudo abrir DesechoOrdersScreen");
}

function findOrdersEntry() {
    const nodes = Array.from(document.querySelectorAll("div, button, a, span"))
        .filter((el) => {
            const txt = (el.textContent || "").trim();
            return txt === "Órdenes" || txt === "Orders";
        });

    if (!nodes.length) {
        return null;
    }

    const entry = nodes[0];
    return entry.closest("div") || entry.parentElement || entry;
}

function ensureHamburgerMenuItem(ctx) {
    if (document.getElementById("btn_pos_desecho_manager_menu")) {
        return true;
    }

    const ordersEntry = findOrdersEntry();
    if (!ordersEntry || !ordersEntry.parentElement) {
        return false;
    }

    const item = document.createElement("div");
    item.id = "btn_pos_desecho_manager_menu";
    item.className = ordersEntry.className || "";
    item.style.cursor = "pointer";
    item.style.display = "flex";
    item.style.justifyContent = "space-between";
    item.style.alignItems = "center";
    item.style.gap = "8px";
    item.style.padding = "10px 12px";
    item.style.marginTop = "2px";

    item.innerHTML = `
        <span>Órdenes de desecho</span>
        <span id="btn_pos_desecho_manager_badge"
              style="background:#17a2b8;color:white;border-radius:10px;padding:0 7px;font-size:12px;min-width:20px;text-align:center;display:none;">
            0
        </span>
    `;

    item.addEventListener("click", () => {
        console.log("[Pasteleria Desechos] click menú gerente");
        openDesechoOrdersScreen(ctx);
    });

    ordersEntry.parentElement.insertBefore(item, ordersEntry.nextSibling);
    console.log("[Pasteleria Desechos] item insertado en hamburguesa ✅");
    return true;
}

function findHamburgerButton() {
    const buttons = Array.from(document.querySelectorAll("button"));
    for (const btn of buttons) {
        const txt = (btn.textContent || "").trim();
        if (txt === "☰" || txt === "≡") {
            return btn;
        }
        const icon = btn.querySelector("i, span");
        if ((icon?.textContent || "").trim() === "☰") {
            return btn;
        }
    }

    // fallback por posición / estilo común
    return buttons.find((btn) => {
        const parentText = (btn.parentElement?.textContent || "").trim();
        return parentText.includes("Gerente") || parentText.includes("Administrador");
    }) || null;
}

function ensureTopbarFallbackButton(ctx) {
    if (document.getElementById("btn_pos_desecho_manager_topbar")) {
        return true;
    }

    const hamburger = findHamburgerButton();
    if (!hamburger || !hamburger.parentElement) {
        return false;
    }

    const btn = document.createElement("button");
    btn.id = "btn_pos_desecho_manager_topbar";
    btn.type = "button";
    btn.textContent = "Desechos";
    btn.style.marginRight = "8px";
    btn.style.padding = "8px 12px";
    btn.style.border = "1px solid #875A7B";
    btn.style.borderRadius = "6px";
    btn.style.background = "#fff";
    btn.style.color = "#875A7B";
    btn.style.fontWeight = "600";
    btn.style.cursor = "pointer";

    btn.addEventListener("click", () => {
        console.log("[Pasteleria Desechos] click botón fallback gerente");
        openDesechoOrdersScreen(ctx);
    });

    hamburger.parentElement.insertBefore(btn, hamburger);
    console.log("[Pasteleria Desechos] botón fallback topbar insertado ✅");
    return true;
}

async function refreshBadge(ctx) {
    try {
        const orm = getOrm(ctx);
        if (!orm) return;

        const count = await orm.searchCount("pasteleria.desecho", [["state", "=", "pending"]]);

        const badgeMenu = document.getElementById("btn_pos_desecho_manager_badge");
        if (badgeMenu) {
            badgeMenu.textContent = String(count || 0);
            badgeMenu.style.display = count ? "inline-block" : "none";
        }

        const topbar = document.getElementById("btn_pos_desecho_manager_topbar");
        if (topbar) {
            topbar.textContent = count ? `Desechos (${count})` : "Desechos";
        }
    } catch (error) {
        console.error("[Pasteleria Desechos] Error actualizando badge:", error);
    }
}

function installMutationObserver(ctx) {
    const observer = new MutationObserver(() => {
        const inserted = ensureHamburgerMenuItem(ctx);
        if (inserted) {
            refreshBadge(ctx);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });

    return observer;
}

export function patchManagerMenu(TargetProto) {
    patch(TargetProto, {
        setup() {
            super.setup();

            onMounted(() => {
                console.log("[Pasteleria Desechos] ProductScreen mounted - manager menu patch activo ✅");

                // fallback visible siempre
                let tries = 0;
                const timer = setInterval(async () => {
                    tries += 1;

                    ensureTopbarFallbackButton(this);
                    ensureHamburgerMenuItem(this);
                    await refreshBadge(this);

                    if (tries >= 60) {
                        clearInterval(timer);
                    }
                }, 500);

                this.__desecho_manager_menu_timer__ = timer;
                this.__desecho_manager_badge_timer__ = setInterval(() => refreshBadge(this), 10000);
                this.__desecho_manager_observer__ = installMutationObserver(this);
            });

            onWillUnmount(() => {
                if (this.__desecho_manager_menu_timer__) {
                    clearInterval(this.__desecho_manager_menu_timer__);
                    this.__desecho_manager_menu_timer__ = null;
                }
                if (this.__desecho_manager_badge_timer__) {
                    clearInterval(this.__desecho_manager_badge_timer__);
                    this.__desecho_manager_badge_timer__ = null;
                }
                if (this.__desecho_manager_observer__) {
                    this.__desecho_manager_observer__.disconnect();
                    this.__desecho_manager_observer__ = null;
                }
            });
        },
    });
}