/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";

function cleanLotName(value) {
    if (!value) {
        return null;
    }
    let text = String(value).trim();
    text = text.replace(/^lot number\s+/i, "").trim();
    return text || null;
}

function extractLotNumberFromLine(line) {
    if (!line) {
        return null;
    }

    if (Array.isArray(line.packLotLines) && line.packLotLines.length) {
        const first = line.packLotLines[0];
        if (typeof first === "string") {
            return cleanLotName(first);
        }
        if (first?.lot_name) {
            return cleanLotName(first.lot_name);
        }
        if (first?.name) {
            return cleanLotName(first.name);
        }
        if (first?.text) {
            return cleanLotName(first.text);
        }
    }

    const directLot =
        line.lotName ||
        line.lot_name ||
        line.customerNote ||
        line.note ||
        line.secondaryText ||
        "";

    if (directLot) {
        return cleanLotName(directLot);
    }

    return null;
}

patch(Orderline.prototype, {
    get expiryIndicatorState() {
        const line = this.props?.line;
        const lotName = extractLotNumberFromLine(line);

        if (!lotName || !this.env?.services?.pos) {
            return null;
        }

        return this.env.services.pos.getLotExpiryInfoByLotName(lotName);
    },
});