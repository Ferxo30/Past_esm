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
            qty: 1,
            lines: [],
            loading: false,
        });
    }

    get selectedProduct() {
        return this.props.products.find(
            (p) => p.id === Number(this.state.selected_product_id)
        );
    }

    addLine() {
        const productId = Number(this.state.selected_product_id);
        const qty = Number(this.state.qty);

        if (!productId || !qty || qty <= 0) {
            this.notification.add("Selecciona producto y una cantidad válida.", {
                type: "warning",
            });
            return;
        }

        const product = this.props.products.find((p) => p.id === productId);
        if (!product) {
            return;
        }

        this.state.lines.push({
            product_id: product.id,
            product_name: product.name,
            qty: qty,
            qty_available: product.qty_available,
            uom_name: product.uom_name,
        });

        this.state.selected_product_id = null;
        this.state.qty = 1;
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