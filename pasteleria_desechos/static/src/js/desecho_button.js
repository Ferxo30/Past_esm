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

function normalizeState(state) {
    const s = (state || "").toLowerCase();
    if (["green", "yellow", "red", "black"].includes(s)) {
        return s;
    }
    return "green";
}

function stateLabel(state) {
    return {
        green: "Verde",
        yellow: "Amarillo",
        red: "Rojo",
        black: "Negro",
    }[normalizeState(state)];
}

function formatDate(value) {
    if (!value) return "—";
    try {
        const d = new Date(value);
        if (!isNaN(d.getTime())) {
            return d.toISOString().slice(0, 10);
        }
    } catch (_) {}
    return String(value);
}

function getLotName(lot) {
    return lot.lot_name || lot.name || lot.display_name || `Lote ${lot.lot_id || ""}`;
}

function getOperationLabel(operationType) {
    return operationType === "gift" ? "regalo" : "desecho";
}

function getOperationLabelTitle(operationType) {
    return operationType === "gift" ? "Regalo" : "Desecho";
}

function operationTypeHtml(selected) {
    return `
        <label class="pd-radio-option">
            <input type="radio" name="pd_operation_type" value="waste" ${selected !== "gift" ? "checked" : ""}/>
            <span>Desecho</span>
        </label>
        <label class="pd-radio-option">
            <input type="radio" name="pd_operation_type" value="gift" ${selected === "gift" ? "checked" : ""}/>
            <span>Regalo</span>
        </label>
    `;
}

function lotsSelectHtml(line) {
    const lots = line.lots || [];
    if (!lots.length) {
        return `<option value="">No hay lotes disponibles</option>`;
    }

    return [
        `<option value="">Seleccionar lote...</option>`,
        ...lots.map((lot) => {
            const selected = Number(line.lot_id) === Number(lot.lot_id) ? "selected" : "";
            const disabled = lot.selectable ? "" : "disabled";
            return `<option value="${lot.lot_id}" ${selected} ${disabled}>
                ${escapeHtml(getLotName(lot))} - Disp: ${escapeHtml(lot.qty_available)} - ${escapeHtml(stateLabel(lot.state))}
            </option>`;
        }),
    ].join("");
}

function lotCardsHtml(line) {
    const lots = line.lots || [];
    if (!lots.length) {
        return `<div class="pd-lots-empty">No hay lotes disponibles para este producto.</div>`;
    }

    return `
        <div class="pd-lots-grid">
            ${lots.map((lot) => {
                const state = normalizeState(lot.state);
                const selected = Number(line.lot_id) === Number(lot.lot_id);
                const selectable = !!lot.selectable;
                return `
                    <div class="pd-lot-card ${selected ? "selected" : ""} ${selectable ? "selectable" : "disabled"}"
                         data-lot-id="${lot.lot_id}">
                        <div class="pd-lot-card-top">
                            <strong>${escapeHtml(getLotName(lot))}</strong>
                            <span class="pd-sem-badge pd-sem-${state}">${escapeHtml(stateLabel(state))}</span>
                        </div>
                        <div class="pd-lot-card-body">
                            <div>Disponible: ${escapeHtml(lot.qty_available)}</div>
                            <div>Vence: ${escapeHtml(formatDate(lot.expiration_date))}</div>
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
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
                    lot_id: false,
                    tracking: p.tracking || "none",
                    lots: [],
                    loading_lots: false,
                    lots_error: "",
                    lots_loaded: false,
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
                    lot_id: false,
                    tracking: p.tracking || "none",
                    lots: [],
                    loading_lots: false,
                    lots_error: "",
                    lots_loaded: false,
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
                lot_id: false,
                tracking: allProducts[0].tracking || "none",
                lots: [],
                loading_lots: false,
                lots_error: "",
                lots_loaded: false,
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

async function loadLotsForLine(ctx, lines, index, rerender) {
    const line = lines[index];
    if (!line || !line.product_id) return;
    if (line.loading_lots) return;

    const orm = getOrm(ctx);
    const posConfigId = getPosConfigId(ctx);
    if (!orm || !posConfigId) return;

    line.loading_lots = true;
    line.lots_error = "";
    line.lots = [];
    line.lot_id = false;
    rerender();

    try {
        const result = await orm.call(
            "pasteleria.desecho",
            "pos_get_product_lots_for_waste",
            [posConfigId, Number(line.product_id)]
        );

        line.tracking = result?.tracking || "none";
        line.lots = result?.lots || [];
        line.lot_id = result?.preferred_lot_id || false;
        line.lots_error = "";
    } catch (error) {
        console.error("[Desecho/Regalo] Error cargando lotes:", error);
        line.lots_error = error?.message || "No se pudieron cargar los lotes.";
    } finally {
        line.loading_lots = false;
        line.lots_loaded = true;
        rerender();
    }
}

function lineRowHtml(index, line, products) {
    const requiresLot = (line.tracking || "none") !== "none";

    return `
        <div class="pd-line" data-line-index="${index}">
            <div class="pd-line-main ${requiresLot ? "with-lot" : "without-lot"}">
                <div class="pd-field pd-product">
                    <label>Producto</label>
                    <select class="pd-input pd-product-select">
                        ${productOptionsHtml(products, line.product_id)}
                    </select>
                </div>

                ${requiresLot ? `
                    <div class="pd-field pd-lot">
                        <label>Lote</label>
                        <select class="pd-input pd-lot-select">
                            ${lotsSelectHtml(line)}
                        </select>
                    </div>
                ` : ""}

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

            ${requiresLot ? `
                <div class="pd-lots-section">
                    <div class="pd-lots-title">Lotes disponibles</div>
                    ${line.loading_lots ? `<div class="pd-lots-loading">Cargando lotes...</div>` : ""}
                    ${line.lots_error ? `<div class="pd-lots-error">${escapeHtml(line.lots_error)}</div>` : ""}
                    ${!line.loading_lots && !line.lots_error ? lotCardsHtml(line) : ""}
                </div>
            ` : ""}
        </div>
    `;
}

function renderModalContent(ctx, root, lines, operationType = "waste") {
    const products = getLoadedProducts(ctx);
    const now = new Date().toLocaleString();
    const cashier = escapeHtml(getCashierName(ctx));
    const posName = escapeHtml(getPosName(ctx));

    const rerender = (newOperationType = operationType) =>
        renderModalContent(ctx, root, lines, newOperationType);

    root.innerHTML = `
        <div class="pasteleria_desecho_overlay">
            <div class="pasteleria_desecho_modal" role="dialog" aria-modal="true" aria-label="Registrar desecho o regalo">
                <div class="pd-header">
                    <div>
                        <h3>Registrar desecho / regalo</h3>
                        <p>El inventario no se moverá hasta que lo confirme el gerente.</p>
                    </div>
                    <button type="button" class="pd-close" aria-label="Cerrar">×</button>
                </div>

                <div class="pd-meta">
                    <div><span>Cajera</span><strong>${cashier || "—"}</strong></div>
                    <div><span>Punto de venta</span><strong>${posName || "—"}</strong></div>
                    <div><span>Fecha</span><strong>${escapeHtml(now)}</strong></div>
                </div>

                <div class="pd-operation-type-box">
                    <div class="pd-operation-type-title">Tipo de operación</div>
                    <div class="pd-operation-type-options">
                        ${operationTypeHtml(operationType)}
                    </div>
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

    root.querySelectorAll('input[name="pd_operation_type"]').forEach((radio) => {
        radio.addEventListener("change", (ev) => {
            const newValue = ev.currentTarget.value || "waste";
            rerender(newValue);
        });
    });

    root.querySelector(".pd-add-line")?.addEventListener("click", () => {
        const firstProduct = products[0] || null;
        lines.push({
            product_id: firstProduct?.id || null,
            qty: 1,
            reason: "",
            lot_id: false,
            tracking: firstProduct?.tracking || "none",
            lots: [],
            loading_lots: false,
            lots_error: "",
            lots_loaded: false,
        });
        rerender(operationType);

        const newIndex = lines.length - 1;
        if (firstProduct && firstProduct.tracking && firstProduct.tracking !== "none") {
            loadLotsForLine(ctx, lines, newIndex, () => rerender(operationType));
        }
    });

    root.querySelectorAll(".pd-line").forEach((lineEl) => {
        const idx = Number(lineEl.dataset.lineIndex || -1);
        if (idx < 0 || !lines[idx]) return;
        const line = lines[idx];

        lineEl.querySelector(".pd-product-select")?.addEventListener("change", async (ev) => {
            const productId = Number(ev.currentTarget.value || 0);
            const product = products.find((p) => Number(p.id) === productId) || null;

            line.product_id = productId || false;
            line.qty = Number(line.qty || 1);
            line.reason = line.reason || "";
            line.lot_id = false;
            line.tracking = product?.tracking || "none";
            line.lots = [];
            line.loading_lots = false;
            line.lots_error = "";
            line.lots_loaded = false;

            rerender(operationType);

            if (productId && product?.tracking && product.tracking !== "none") {
                await loadLotsForLine(ctx, lines, idx, () => rerender(operationType));
            }
        });

        lineEl.querySelector(".pd-qty-input")?.addEventListener("input", (ev) => {
            line.qty = Number(ev.currentTarget.value || 0);
        });

        lineEl.querySelector(".pd-reason-input")?.addEventListener("input", (ev) => {
            line.reason = ev.currentTarget.value || "";
        });

        lineEl.querySelector(".pd-remove-line")?.addEventListener("click", () => {
            lines.splice(idx, 1);
            rerender(operationType);
        });

        lineEl.querySelector(".pd-lot-select")?.addEventListener("change", (ev) => {
            line.lot_id = Number(ev.currentTarget.value || 0) || false;
            rerender(operationType);
        });

        lineEl.querySelectorAll(".pd-lot-card.selectable").forEach((card) => {
            card.addEventListener("click", () => {
                const lotId = Number(card.dataset.lotId || 0);
                line.lot_id = lotId || false;
                rerender(operationType);
            });
        });
    });

    root.querySelector(".pd-submit")?.addEventListener("click", async () => {
        const errorBox = root.querySelector(".pd-error");

        const payloadLines = lines
            .map((line) => ({
                product_id: Number(line.product_id || 0),
                lot_id: line.tracking !== "none" ? (Number(line.lot_id || 0) || false) : false,
                qty: Number(line.qty || 0),
                reason: String(line.reason || "").trim(),
                tracking: line.tracking || "none",
                lots: line.lots || [],
            }))
            .filter((line) => line.product_id && line.qty > 0);

        if (!payloadLines.length) {
            errorBox.textContent = "Debes agregar al menos una línea con cantidad mayor a 0.";
            errorBox.style.display = "block";
            return;
        }

        for (const line of payloadLines) {
            if (line.tracking !== "none" && !line.lot_id) {
                errorBox.textContent = "Hay productos con lote obligatorio y aún no seleccionaste lote.";
                errorBox.style.display = "block";
                return;
            }

            if (line.tracking !== "none") {
                const lot = (line.lots || []).find((l) => Number(l.lot_id) === Number(line.lot_id));
                if (!lot) {
                    errorBox.textContent = "Uno de los lotes seleccionados ya no es válido.";
                    errorBox.style.display = "block";
                    return;
                }
                if (Number(line.qty) > Number(lot.qty_available || 0)) {
                    errorBox.textContent = `La cantidad no puede ser mayor al disponible del lote ${getLotName(lot)}.`;
                    errorBox.style.display = "block";
                    return;
                }
            }
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
                    operation_type: operationType,
                    lines: payloadLines.map((l) => ({
                        product_id: l.product_id,
                        lot_id: l.lot_id || false,
                        qty: l.qty,
                        reason: l.reason,
                    })),
                },
            ]);

            close();
            showToast(
                `${getOperationLabelTitle(res.operation_type || operationType)} ${res.name} creado y enviado a aprobación.`
            );
        } catch (error) {
            console.error("[Desecho/Regalo] Error creando solicitud:", error);
            errorBox.textContent = error?.message || "No se pudo crear la solicitud. Revisa servidor.";
            errorBox.style.display = "block";
            submitBtn.disabled = false;
            submitBtn.textContent = "Crear solicitud";
        }
    });

    lines.forEach((line, idx) => {
        if (!line || !line.product_id) return;
        if ((line.tracking || "none") === "none") return;
        if (line.loading_lots) return;
        if (line.lots_loaded) return;
        loadLotsForLine(ctx, lines, idx, () => rerender(operationType));
    });
}

function openDesechoModal(ctx) {
    const lines = buildInitialLines(ctx);
    if (!lines.length) {
        window.alert("No hay líneas o productos disponibles para registrar desecho o regalo.");
        return;
    }

    const root = ensureModalRoot();
    renderModalContent(ctx, root, lines, "waste");
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
    btn.textContent = "Desecho / Regalo";
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