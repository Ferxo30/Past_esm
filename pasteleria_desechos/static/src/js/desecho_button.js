/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onMounted, onWillUnmount } from "@odoo/owl";

console.log("[Pasteleria Desechos] desecho_button.js cargado ✅");

const _superSetup = ProductScreen.prototype.setup;

function getOrder(ctx) {
    return ctx.pos?.get_order?.() || ctx.currentOrder || ctx.env?.pos?.get_order?.() || null;
}

function getOrderLines(order) {
    if (!order) return [];
    if (typeof order.get_orderlines === "function") return order.get_orderlines() || [];
    if (order.orderlines?.models) return order.orderlines.models || [];
    return [];
}

function getSelectedOrderLine(order) {
    if (!order) return null;
    if (typeof order.get_selected_orderline === "function") return order.get_selected_orderline();
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
    if (line.product_id && typeof line.product_id === "object") return line.product_id;
    return null;
}

function getQtyFromLine(line) {
    if (!line) return 1;
    if (typeof line.get_quantity === "function") return Number(line.get_quantity() || 0);
    return Number(line.qty || 0);
}

function getOrm(ctx) {
    return ctx.env?.services?.orm || ctx.orm || null;
}

function getPosConfigId(ctx) {
    return ctx.pos?.config?.id || ctx.env?.pos?.config?.id || null;
}

function getCashierName(ctx) {
    return ctx.pos?.get_cashier?.()?.name || ctx.pos?.user?.name || "";
}

function getPosName(ctx) {
    return ctx.pos?.config?.name || ctx.env?.pos?.config?.name || "";
}

function getLoadedProducts(ctx) {
    const candidates = [];

    const dbProducts = ctx.pos?.db?.product_by_id || ctx.env?.pos?.db?.product_by_id || {};
    if (dbProducts && Object.keys(dbProducts).length) {
        candidates.push(...Object.values(dbProducts).filter(Boolean));
    }

    const order = getOrder(ctx);
    const orderLines = getOrderLines(order);
    for (const line of orderLines) {
        const p = getProductFromLine(line);
        if (p) {
            candidates.push(p);
        }
    }

    const unique = [];
    const seen = new Set();
    for (const p of candidates) {
        if (p && p.id && !seen.has(p.id)) {
            seen.add(p.id);
            unique.push(p);
        }
    }

    return unique.sort((a, b) => {
        const an = (a.display_name || a.name || "").toLowerCase();
        const bn = (b.display_name || b.name || "").toLowerCase();
        return an.localeCompare(bn);
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function productOptionsHtml(products, selectedId) {
    return products
        .map((p) => {
            const sel = Number(selectedId) === Number(p.id) ? "selected" : "";
            return `<option value="${p.id}" ${sel}>${escapeHtml(
                p.display_name || p.name || ("Producto " + p.id)
            )}</option>`;
        })
        .join("");
}

function buildInitialLines(ctx) {
    const order = getOrder(ctx);

    const selectedLine = getSelectedOrderLine(order);
    if (selectedLine) {
        const p = getProductFromLine(selectedLine);
        if (p) {
            return [
                {
                    product_id: p.id,
                    qty: Math.max(1, getQtyFromLine(selectedLine) || 1),
                    reason: "",
                },
            ];
        }
    }

    const orderLines = getOrderLines(order);
    if (orderLines.length) {
        return orderLines
            .map((line) => {
                const p = getProductFromLine(line);
                if (!p) return null;
                return {
                    product_id: p.id,
                    qty: Math.max(1, getQtyFromLine(line) || 1),
                    reason: "",
                };
            })
            .filter(Boolean);
    }

    const allProducts = getLoadedProducts(ctx);
    if (allProducts.length) {
        return [
            {
                product_id: allProducts[0].id,
                qty: 1,
                reason: "",
            },
        ];
    }

    return [];
}

function ensureModalRoot() {
    let root = document.getElementById("pasteleria_desecho_modal_root");
    if (!root) {
        root = document.createElement("div");
        root.id = "pasteleria_desecho_modal_root";
        document.body.appendChild(root);
    }
    return root;
}

function removeModal() {
    const root = document.getElementById("pasteleria_desecho_modal_root");
    if (root) {
        root.innerHTML = "";
        root.classList.remove("show");
    }
    document.body.classList.remove("pasteleria-desecho-modal-open");
}

function showToast(message, isError = false) {
    const root = ensureModalRoot();
    const toast = document.createElement("div");
    toast.className = "pasteleria_desecho_toast" + (isError ? " error" : "");
    toast.textContent = message;
    root.appendChild(toast);

    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 250);
    }, 2600);
}

function lineRowHtml(index, line, products) {
    return `
        <div class="pd-line" data-line-index="${index}">
            <div class="pd-field pd-product">
                <label>Producto</label>
                <select class="pd-input pd-product-select">
                    ${productOptionsHtml(products, line.product_id)}
                </select>
            </div>
            <div class="pd-field pd-qty">
                <label>Cantidad</label>
                <input class="pd-input pd-qty-input" type="number" min="0.01" step="0.01" value="${escapeHtml(line.qty || 1)}" />
            </div>
            <div class="pd-field pd-reason">
                <label>Motivo</label>
                <input class="pd-input pd-reason-input" type="text" value="${escapeHtml(line.reason || "")}" placeholder="Opcional" />
            </div>
            <div class="pd-field pd-remove-wrap">
                <label>&nbsp;</label>
                <button type="button" class="pd-remove-line">Quitar</button>
            </div>
        </div>
    `;
}

function renderModalContent(ctx, root, lines) {
    const products = getLoadedProducts(ctx);
    const now = new Date().toLocaleString();
    const cashier = escapeHtml(getCashierName(ctx));
    const posName = escapeHtml(getPosName(ctx));

    root.innerHTML = `
        <div class="pasteleria_desecho_overlay">
            <div class="pasteleria_desecho_modal" role="dialog" aria-modal="true" aria-label="Registrar desecho">
                <div class="pd-header">
                    <div>
                        <h3>Registrar desecho</h3>
                        <p>El inventario no se descontará hasta que lo confirme el gerente.</p>
                    </div>
                    <button type="button" class="pd-close" aria-label="Cerrar">×</button>
                </div>

                <div class="pd-meta">
                    <div><span>Cajera</span><strong>${cashier || "—"}</strong></div>
                    <div><span>Punto de venta</span><strong>${posName || "—"}</strong></div>
                    <div><span>Fecha</span><strong>${escapeHtml(now)}</strong></div>
                </div>

                <div class="pd-error" style="display:none;"></div>

                <div class="pd-lines">
                    ${lines.map((line, index) => lineRowHtml(index, line, products)).join("")}
                </div>

                <div class="pd-actions-row">
                    <button type="button" class="pd-secondary pd-add-line">+ Agregar línea</button>
                </div>

                <div class="pd-footer">
                    <button type="button" class="pd-secondary pd-cancel">Cancelar</button>
                    <button type="button" class="pd-primary pd-submit">Crear solicitud</button>
                </div>
            </div>
        </div>
    `;

    root.classList.add("show");
    document.body.classList.add("pasteleria-desecho-modal-open");

    const close = () => removeModal();

    root.querySelector(".pd-close")?.addEventListener("click", close);
    root.querySelector(".pd-cancel")?.addEventListener("click", close);
    root.querySelector(".pasteleria_desecho_overlay")?.addEventListener("click", (ev) => {
        if (ev.target.classList.contains("pasteleria_desecho_overlay")) {
            close();
        }
    });

    root.querySelector(".pd-add-line")?.addEventListener("click", () => {
        const firstProductId = products[0]?.id || null;
        lines.push({
            product_id: firstProductId,
            qty: 1,
            reason: "",
        });
        renderModalContent(ctx, root, lines);
    });

    root.querySelectorAll(".pd-remove-line").forEach((btn) => {
        btn.addEventListener("click", (ev) => {
            const lineEl = ev.currentTarget.closest(".pd-line");
            const idx = Number(lineEl?.dataset?.lineIndex ?? -1);
            if (idx >= 0) {
                lines.splice(idx, 1);
                renderModalContent(ctx, root, lines);
            }
        });
    });

    root.querySelector(".pd-submit")?.addEventListener("click", async () => {
        const errorBox = root.querySelector(".pd-error");
        const rowEls = Array.from(root.querySelectorAll(".pd-line"));

        const payloadLines = rowEls
            .map((row) => ({
                product_id: Number(row.querySelector(".pd-product-select")?.value || 0),
                qty: Number(row.querySelector(".pd-qty-input")?.value || 0),
                reason: (row.querySelector(".pd-reason-input")?.value || "").trim(),
            }))
            .filter((line) => line.product_id && line.qty > 0);

        if (!payloadLines.length) {
            errorBox.textContent = "Debes agregar al menos una línea con cantidad mayor a 0.";
            errorBox.style.display = "block";
            return;
        }

        const orm = getOrm(ctx);
        const posConfigId = getPosConfigId(ctx);

        if (!orm || !posConfigId) {
            errorBox.textContent = "No se pudo determinar el servicio ORM o el punto de venta.";
            errorBox.style.display = "block";
            return;
        }

        const submitBtn = root.querySelector(".pd-submit");
        submitBtn.disabled = true;
        submitBtn.textContent = "Creando...";

        try {
            const res = await orm.call("pasteleria.desecho", "create_from_pos", [
                {
                    pos_config_id: posConfigId,
                    lines: payloadLines,
                },
            ]);

            close();
            showToast(`Desecho ${res.name} creado y enviado a aprobación.`);
        } catch (error) {
            console.error("[Desecho] Error creando solicitud:", error);
            errorBox.textContent = error?.message || "No se pudo crear el desecho. Revisa servidor.";
            errorBox.style.display = "block";
            submitBtn.disabled = false;
            submitBtn.textContent = "Crear solicitud";
        }
    });
}

function openDesechoModal(ctx) {
    const lines = buildInitialLines(ctx);
    if (!lines.length) {
        window.alert("No hay líneas o productos disponibles para registrar desecho.");
        return;
    }

    const root = ensureModalRoot();
    renderModalContent(ctx, root, lines);
}

function findPayButtonElement() {
    const nodes = Array.from(document.querySelectorAll("button,div,span,a"));
    const byText = nodes.find((n) => (n.textContent || "").trim() === "Pago");
    return byText ? byText.closest("button") || byText : null;
}

function ensureDesechoButton(ctx) {
    if (document.getElementById("btn_pasteleria_desecho")) return true;

    const payEl = findPayButtonElement();
    if (!payEl || !payEl.parentElement) return false;

    const btn = document.createElement("button");
    btn.id = "btn_pasteleria_desecho";
    btn.type = "button";
    btn.textContent = "Desecho";
    btn.className = "pasteleria_desecho_trigger_btn";
    btn.addEventListener("click", () => ctx.onClickPasteleriaDesecho());

    payEl.parentElement.insertBefore(btn, payEl);
    return true;
}

patch(ProductScreen.prototype, {
    setup() {
        _superSetup.call(this, ...arguments);

        onMounted(() => {
            let tries = 0;
            const timer = setInterval(() => {
                tries += 1;
                const ok = ensureDesechoButton(this);
                if (ok || tries >= 30) {
                    clearInterval(timer);
                }
            }, 200);
            this.__pasteleria_desecho_timer__ = timer;
        });

        onWillUnmount(() => {
            if (this.__pasteleria_desecho_timer__) {
                clearInterval(this.__pasteleria_desecho_timer__);
                this.__pasteleria_desecho_timer__ = null;
            }
            removeModal();
        });
    },

    async onClickPasteleriaDesecho() {
        openDesechoModal(this);
    },
});