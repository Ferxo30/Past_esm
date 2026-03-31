/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class TransferPopup extends Component {
    static template = "pasteleria_pos_transferencias.TransferPopup";
    static components = { Dialog };
    static props = {
        close: Function,
        originPosId: Number,
        originPosName: String,
        destinations: Array,
        products: Array,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            destination_pos_id: null,
            selected_product_id: null,
            selected_lot_id: null,
            qty: 1,
            lots: [],
            loadingLots: false,
            lines: [],
            loading: false,
        });
    }

    get selectedProduct() {
        return this.props.products.find(
            (p) => p.id === Number(this.state.selected_product_id)
        );
    }

    get selectableLots() {
        return this.state.lots || [];
    }

    getStateLabel(state) {
        const map = {
            green: "Verde",
            yellow: "Amarillo",
            red: "Rojo",
            black: "Negro",
        };
        return map[state] || state || "";
    }

    getStateClass(state) {
        return `o_transfer_lot_state o_transfer_lot_state_${state || "none"}`;
    }

    async onProductChange() {
        this.state.selected_lot_id = null;
        this.state.lots = [];

        if (!this.state.selected_product_id) {
            return;
        }

        this.state.loadingLots = true;

        try {
            const result = await this.orm.call(
                "pasteleria.pos.transfer",
                "pos_get_product_lots_for_transfer",
                [
                    this.props.originPosId,
                    Number(this.state.selected_product_id),
                ]
            );

            this.state.lots = result.lots || [];

            if (result.preferred_lot_id) {
                const preferred = this.state.lots.find(
                    (lot) => lot.lot_id === result.preferred_lot_id && lot.selectable
                );
                if (preferred) {
                    this.state.selected_lot_id = preferred.lot_id;
                }
            }
        } catch (error) {
            console.error("[Pasteleria Transferencias] Error cargando lotes:", error);
            this.notification.add(
                error?.data?.message || error?.message || "No se pudieron cargar los lotes.",
                { type: "danger" }
            );
        } finally {
            this.state.loadingLots = false;
        }
    }

    addLine() {
        const productId = Number(this.state.selected_product_id);
        const lotId = Number(this.state.selected_lot_id);
        const qty = Number(this.state.qty);

        if (!productId) {
            this.notification.add("Debes seleccionar un producto.", {
                type: "warning",
            });
            return;
        }

        if (!lotId) {
            this.notification.add("Debes seleccionar un lote.", {
                type: "warning",
            });
            return;
        }

        if (!qty || qty <= 0) {
            this.notification.add("Debes ingresar una cantidad válida.", {
                type: "warning",
            });
            return;
        }

        const product = this.props.products.find((p) => p.id === productId);
        const lot = this.state.lots.find((l) => l.lot_id === lotId);

        if (!product || !lot) {
            this.notification.add("No se encontró el producto o lote seleccionado.", {
                type: "warning",
            });
            return;
        }

        if (!lot.selectable) {
            this.notification.add("Ese lote no se puede transferir.", {
                type: "warning",
            });
            return;
        }

        if (qty > Number(lot.qty_available || 0)) {
            this.notification.add("La cantidad excede lo disponible en el lote.", {
                type: "warning",
            });
            return;
        }

        const duplicate = this.state.lines.find(
            (line) => line.product_id === productId && line.lot_id === lotId
        );

        if (duplicate) {
            duplicate.qty = Number(duplicate.qty) + qty;
        } else {
            this.state.lines.push({
                product_id: product.id,
                product_name: product.name,
                lot_id: lot.lot_id,
                lot_name: lot.lot_name,
                expiration_date: lot.expiration_date,
                state: lot.state,
                qty_available: lot.qty_available,
                qty: qty,
                uom_name: product.uom_name,
            });
        }

        this.state.selected_product_id = null;
        this.state.selected_lot_id = null;
        this.state.qty = 1;
        this.state.lots = [];
    }

    removeLine(index) {
        this.state.lines.splice(index, 1);
    }

    async confirmTransfer() {
        if (!this.state.destination_pos_id) {
            this.notification.add("Debes seleccionar un POS destino.", {
                type: "warning",
            });
            return;
        }

        if (!this.state.lines.length) {
            this.notification.add("Debes agregar al menos una línea.", {
                type: "warning",
            });
            return;
        }

        this.state.loading = true;

        try {
            const result = await this.orm.call(
                "pasteleria.pos.transfer",
                "pos_create_transfer_from_ui",
                [{
                    origin_pos_id: this.props.originPosId,
                    destination_pos_id: Number(this.state.destination_pos_id),
                    lines: this.state.lines.map((line) => ({
                        product_id: line.product_id,
                        lot_id: line.lot_id,
                        qty: line.qty,
                    })),
                }]
            );

            this.notification.add(
                `Transferencia ${result.transfer_name} creada correctamente.`,
                { type: "success" }
            );

            this.props.close();
        } catch (error) {
            console.error("[Pasteleria Transferencias] Error creando transferencia:", error);
            this.notification.add(
                error?.data?.message || error?.message || "No se pudo crear la transferencia.",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }
}