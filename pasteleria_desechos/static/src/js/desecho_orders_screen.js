/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patchManagerMenu } from "./desecho_manager_button";

console.log("[Pasteleria Desechos] desecho_orders_screen.js cargado ✅");

patchManagerMenu(ProductScreen.prototype);

export class DesechoOrdersScreen extends Component {
    static template = "pasteleria_desechos.DesechoOrdersScreen";

    setup() {
        this.orm = useService("orm");
        this.pos = useService("pos");

        this.state = useState({
            orders: [],
            loading: true,
            error: "",
        });

        // Bind explícito para que no se pierda el contexto en los botones
        this.loadOrders = this.loadOrders.bind(this);
        this.confirmOrder = this.confirmOrder.bind(this);
        this.rejectOrder = this.rejectOrder.bind(this);
        this.goBack = this.goBack.bind(this);

        onWillStart(async () => {
            await this.loadOrders();
        });
    }

    async loadOrders() {
        this.state.loading = true;
        this.state.error = "";

        try {
            const orders = await this.orm.searchRead(
                "pasteleria.desecho",
                [["state", "=", "pending"]],
                [
                    "name",
                    "requested_by",
                    "requested_date",
                    "total_qty",
                    "warehouse_id",
                    "pos_config_id",
                ]
            );

            this.state.orders = orders || [];
        } catch (error) {
            console.error("[Pasteleria Desechos] Error cargando desechos:", error);
            this.state.error = error?.message || "No se pudieron cargar los desechos.";
        } finally {
            this.state.loading = false;
        }
    }

    async confirmOrder(order) {
        try {
            console.log("[Pasteleria Desechos] Confirmando desecho:", order);

            await this.orm.call(
                "pasteleria.desecho",
                "action_confirm",
                [[order.id]]
            );

            await this.loadOrders();
        } catch (error) {
            console.error("[Pasteleria Desechos] Error confirmando desecho:", error);
            window.alert("No se pudo confirmar el desecho.");
        }
    }

    async rejectOrder(order) {
        try {
            console.log("[Pasteleria Desechos] Rechazando desecho:", order);

            await this.orm.call(
                "pasteleria.desecho",
                "action_reject",
                [[order.id]]
            );

            await this.loadOrders();
        } catch (error) {
            console.error("[Pasteleria Desechos] Error rechazando desecho:", error);
            window.alert("No se pudo rechazar el desecho.");
        }
    }

    goBack() {
        if (this.pos && typeof this.pos.showScreen === "function") {
            this.pos.showScreen("ProductScreen");
        } else {
            console.error("[Pasteleria Desechos] No se pudo volver a ProductScreen");
        }
    }
}

registry.category("pos_screens").add("DesechoOrdersScreen", DesechoOrdersScreen);