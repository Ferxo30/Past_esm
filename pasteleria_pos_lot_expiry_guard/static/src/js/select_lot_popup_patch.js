/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { EditListPopup } from "@point_of_sale/app/store/select_lot_popup/select_lot_popup";
import { EditListInput } from "@point_of_sale/app/store/select_lot_popup/edit_list_input/edit_list_input";
import { makeAwaitable, ask } from "@point_of_sale/app/store/make_awaitable_dialog";

console.log("[POS LOT EXPIRY] select_lot_popup_patch.js cargado ✅");

EditListPopup.props = {
    ...EditListPopup.props,
    getOptionMeta: { type: Function, optional: true },
};

EditListInput.props = {
    ...EditListInput.props,
    getOptionMeta: { type: Function, optional: true },
};

patch(EditListInput.prototype, {
    get optionMeta() {
        const getOptionMeta = this.props?.getOptionMeta;
        const text = this.props?.item?.text;
        if (!getOptionMeta || !text) {
            return null;
        }
        return getOptionMeta(text);
    },

    getDisplayedOptionMeta(option) {
        const getOptionMeta = this.props?.getOptionMeta;
        return getOptionMeta ? getOptionMeta(option) : null;
    },
});

patch(PosStore.prototype, {
    async editLots(product, packLotLinesToEdit) {
        const isAllowOnlyOneLot = product.isAllowOnlyOneLot();
        let canCreateLots = this.pickingType.use_create_lots || !this.pickingType.use_existing_lots;

        let existingLots = [];
        try {
            existingLots = await this.data.call(
                "pos.order.line",
                "get_existing_lots",
                [this.company.id, product.id],
                {
                    context: {
                        config_id: this.config.id,
                    },
                }
            );

            this.setLotExpiryMetadata(product.id, existingLots);

            if (!canCreateLots && (!existingLots || existingLots.length === 0)) {
                this.dialog.add(AlertDialog, {
                    title: _t("No existing serial/lot number"),
                    body: _t(
                        "There is no serial/lot number for the selected product, and their creation is not allowed from the Point of Sale app."
                    ),
                });
                return null;
            }
        } catch (ex) {
            console.error("[POS LOT EXPIRY] Collecting existing lots failed:", ex);
            const confirmed = await ask(this.dialog, {
                title: _t("Server communication problem"),
                body: _t(
                    "The existing serial/lot numbers could not be retrieved. \nContinue without checking the validity of serial/lot numbers ?"
                ),
                confirmLabel: _t("Yes"),
                cancelLabel: _t("No"),
            });
            if (!confirmed) {
                return null;
            }
            canCreateLots = true;
        }

        const usedLotsQty = this.models["pos.pack.operation.lot"]
            .filter(
                (lot) =>
                    lot.pos_order_line_id?.product_id?.id === product.id &&
                    lot.pos_order_line_id?.order_id?.state === "draft"
            )
            .reduce((acc, lot) => {
                if (!acc[lot.lot_name]) {
                    acc[lot.lot_name] = { total: 0, currentOrderCount: 0 };
                }
                acc[lot.lot_name].total += lot.pos_order_line_id?.qty || 0;

                if (lot.pos_order_line_id?.order_id?.id === this.selectedOrder.id) {
                    acc[lot.lot_name].currentOrderCount += lot.pos_order_line_id?.qty || 0;
                }
                return acc;
            }, {});

        existingLots = existingLots.filter(
            (lot) => lot.product_qty > (usedLotsQty[lot.name]?.total || 0)
        );

        this.setLotExpiryMetadata(product.id, existingLots);

        const isLotNameUsed = (itemValue) => {
            const totalQty = existingLots.find((lt) => lt.name == itemValue)?.product_qty || 0;
            const usedQty = usedLotsQty[itemValue]
                ? usedLotsQty[itemValue].total - usedLotsQty[itemValue].currentOrderCount
                : 0;
            return usedQty ? usedQty >= totalQty : false;
        };

        const existingLotsName = existingLots.map((l) => l.name);

        if (!packLotLinesToEdit.length && existingLotsName.length === 1) {
            return { newPackLotLines: [{ lot_name: existingLotsName[0] }] };
        }

        const payload = await makeAwaitable(this.dialog, EditListPopup, {
            title: _t("Lot/Serial Number(s) Required"),
            name: product.display_name,
            isSingleItem: isAllowOnlyOneLot,
            array: packLotLinesToEdit,
            options: existingLotsName,
            customInput: canCreateLots,
            uniqueValues: product.tracking === "serial",
            isLotNameUsed: isLotNameUsed,
            getOptionMeta: (lotName) => {
                const lot = existingLots.find((x) => x.name === lotName);
                if (!lot) {
                    return null;
                }
                return {
                    state: lot.state || "green",
                    expired: !!lot.expired,
                    sellable: !!lot.sellable,
                    expiration_date: lot.expiration_date || false,
                };
            },
        });

        console.log("[POS LOT EXPIRY] raw lot popup payload =>", payload);

        if (payload) {
            const modifiedPackLotLines = Object.fromEntries(
                payload.filter((item) => item.id).map((item) => [item.id, item.text])
            );
            const newPackLotLines = payload
                .filter((item) => !item.id)
                .map((item) => ({ lot_name: item.text }));

            return { modifiedPackLotLines, newPackLotLines };
        } else {
            return null;
        }
    },
});