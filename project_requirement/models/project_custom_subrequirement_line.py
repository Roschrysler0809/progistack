from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectCustomSubrequirementLine(models.Model):
    """
    This model represents a custom subrequirement line in a project custom requirement line.
    Each custom subrequirement line belongs to a custom requirement line and contains a custom name.
    """
    _name = 'project.custom.subrequirement.line'
    _inherit = ['project.abstract.subrequirement.line']
    _description = "Ligne de sous-exigence personnalisée"
    _order = 'custom_requirement_line_id, order, id'

    # Specific fields for custom subrequirement lines
    custom_requirement_line_id = fields.Many2one('project.custom.requirement.line',
                                                 string="Ligne d'exigence personnalisée",
                                                 required=True, ondelete='cascade')
    department_id = fields.Many2one(related='custom_requirement_line_id.department_id', string="Département",
                                    readonly=True, store=True)
    project_stage = fields.Selection(related='custom_requirement_line_id.project_stage',
                                     string="Étape du projet", readonly=True)
    name = fields.Char(string="Sous-exigence", required=True,
                       help="Nom personnalisé de la sous-exigence")

    # Add related fields from project for view conditions
    parent_project_type = fields.Selection(related='custom_requirement_line_id.project_id.project_type',
                                           string="Type de projet parent", readonly=True)

    @api.depends('department_id', 'name')
    def _compute_display_name(self):
        """Compute display name based on department and custom name"""
        for record in self:
            display_parts = []

            # Always include the department if available
            if record.department_id:
                display_parts.append(record.department_id.name)

            # Add the custom name
            if record.name:
                display_parts.append(record.name)

            # Create the display name with parts joined by a separator
            record.display_name = " - ".join(display_parts) if display_parts else "Ligne de sous-exigence personnalisée"

    def open_form(self):
        """Opens the custom subrequirement line form view."""
        self.ensure_one()

        # Check if the project is in project stage and not an etude_chiffrage project
        if self.project_stage == 'project' and self.parent_project_type != 'etude_chiffrage':
            raise UserError(_("Impossible de modifier une ligne de sous-exigence personnalisée en phase projet."))

        return {
            'name': _('Modifier la ligne de sous-exigence personnalisée'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.custom.subrequirement.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }

    def _trim_trailing_spaces(self, vals):
        """
        Trim trailing spaces from name field in vals dict
        """
        if vals.get('name'):
            vals['name'] = vals['name'].rstrip()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle department from parent requirement line."""
        # Trim trailing spaces in name field
        for vals in vals_list:
            self._trim_trailing_spaces(vals)

        result = super(ProjectCustomSubrequirementLine, self).create(vals_list)

        # Force recomputation of parent requirement line estimated work days
        self._update_parent_requirement_line()

        return result

    def write(self, vals):
        """Override write to update parent requirement line when estimated days change."""
        # Trim trailing spaces in name field
        self._trim_trailing_spaces(vals)

        # Execute the standard update
        result = super().write(vals)

        # Force recomputation of parent requirement line if estimated_work_days changed
        if 'estimated_work_days' in vals:
            self._update_parent_requirement_line()

        return result

    def unlink(self):
        """Override unlink to trigger recalculation on parent requirement line."""
        # Store requirement lines before deletion
        requirement_lines = self.mapped('custom_requirement_line_id')

        # Delete the records
        result = super().unlink()

        # Trigger recomputation on parent requirement lines
        if requirement_lines:
            requirement_lines._compute_estimated_work_days()
            requirement_lines._compute_planned_dates()
            requirement_lines._compute_estimated_days()

    def _get_concrete_model_name(self):
        """Return the technical name of this model"""
        return 'project.custom.subrequirement.line'

    def _get_parent_requirement_field_name(self):
        """Return the field name that points to the parent requirement line"""
        return 'custom_requirement_line_id'
