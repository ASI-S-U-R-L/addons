/** @odoo-module **/

import { Field } from "@web/views/fields/field";
import { registry } from "@web/core/registry";

export class DenominationsTableWidget extends Field {
    static template = "asi_pos_options.DenominationsTableWidget";

    get denominationsData() {
        try {
            const value = this.props.record.data[this.props.name];
            if (!value) return [];

            const parsed = JSON.parse(value);
            if (parsed && parsed.denominations && Array.isArray(parsed.denominations)) {
                return parsed.denominations;
            }
            return [];
        } catch (e) {
            console.warn("Error parsing denominations data:", e);
            return [];
        }
    }

    get totalAmount() {
        try {
            const value = this.props.record.data[this.props.name];
            if (!value) return 0;

            const parsed = JSON.parse(value);
            return parsed.total || 0;
        } catch (e) {
            return 0;
        }
    }
}

registry.category("fields").add("denominations_table", DenominationsTableWidget);