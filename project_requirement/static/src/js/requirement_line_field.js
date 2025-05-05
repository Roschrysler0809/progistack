/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _lt } from "@web/core/l10n/translation";
import { _t } from "@web/core/l10n/translation";

/**
 * RequirementLineTextField - A widget for requirement_id that shows description underneath
 * Instead of extending Many2OneField, we wrap it as a child component
 */
export class RequirementLineTextField extends Component {
    static template = "project_requirement.RequirementLineTextField";
    static props = standardFieldProps;
    static components = { Many2OneField };

    setup() {
        this.state = useState({
            description: this.props.record.data.description || ''
        });
        this.root = useRef("root");
        
        // Create props for the Many2OneField component but don't modify the domain
        this.many2oneProps = { ...this.props };
    }
    
    /**
     * Check if the record has a description
     */
    hasDescription() {
        return Boolean(this.props.record.data.description);
    }
    
    /**
     * Get the description text
     */
    getDescription() {
        return this.props.record.data.description || "";
    }

    /**
     * Add description button handler - uses requirement name as default
     */
    onAddDescription(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        // Get requirement name and use it as default description
        const reqName = this.props.record.data.requirement_id ? this.props.record.data.requirement_id[1] : "";
        if (reqName) {
            this.props.record.update({ description: reqName });
        } else {
            this.props.record.update({ description: "" });
        }
        
        // Focus the input after a short delay to ensure it's rendered
        setTimeout(() => {
            const input = this.root.el.querySelector('.o_description_input');
            if (input) {
                input.focus();
            }
        }, 50);
    }

    /**
     * Update description when focus is lost
     */
    onDescriptionBlur(ev) {
        const description = ev.target.value;
        if (description !== this.props.record.data.description) {
            this.props.record.update({ description });
        }
    }
    
    /**
     * Handle keydown events in the description input
     * For single-line inputs, Enter completes the edit
     */
    onDescriptionKeydown(ev) {
        if (ev.key === "Enter") {
            // Save the description
            const description = ev.target.value;
            if (description !== this.props.record.data.description) {
                this.props.record.update({ description });
            }
            
            // Move focus to the next field
            ev.target.blur();
            ev.preventDefault();
            ev.stopPropagation();
        }
    }
}

registry.category("fields").add("requirement_line_text", {
    component: RequirementLineTextField,
});

// Remove the list-specific registration as it's not needed
// registry.category('fields').add('list.requirement_line_text', listRequirementLineTextField); 