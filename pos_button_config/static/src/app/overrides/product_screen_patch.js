/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        const config = this.pos?.config || {};

        return buttons.map((button) => {
            const value = button.value;
            const disabledByConfig =
                (value === "quantity" && !config.wv_qty) ||
                (value === "discount" && !config.wv_discount) ||
                (value === "price" && !config.wv_price) ||
                (value === "-" && !config.wv_plusminus);

            return {
                ...button,
                disabled: Boolean(button.disabled || disabledByConfig),
            };
        });
    },
});
