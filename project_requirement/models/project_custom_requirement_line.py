from odoo import models, fields, api
from odoo.exceptions import ValidationError
from .common_projects import get_generic_department


class ProjectCustomRequirementLine(models.Model):
    """
    This model represents a custom requirement line in an evolution project.
    Each custom requirement line belongs to a project and contains a custom requirement name (text field).
    It can contain multiple custom subrequirement lines.
    Requirements are organized by order which determines their planned start and end dates.
    """
    _name = 'project.custom.requirement.line'
    _inherit = 'project.abstract.requirement.line'
    _description = "Ligne d'exigence personnalisée du projet"
    _order = 'order, planned_end_date, id'
    _rec_name = 'display_name'

    # Type selection matching the regular requirement model
    TYPE_SELECTION = [
        ('internal', 'Exigence Interne'),
        ('external', 'Exigence Externe')
    ]

    # Fields specific to custom requirement lines
    name = fields.Char(string="Exigence", required=True,
                       help="Nom personnalisé de l'exigence pour les projets d'évolution")
    type = fields.Selection(TYPE_SELECTION, string="Type", required=True, default='external')
    department_id = fields.Many2one('project.department', string="Département", required=True,
                                    default=lambda self: self._get_generic_department())
    custom_subrequirement_line_ids = fields.One2many('project.custom.subrequirement.line', 'custom_requirement_line_id',
                                                     string="Lignes de sous-exigences personnalisées")

    has_modified_subrequirements = fields.Boolean(string="Sous-exigences modifiées",
                                                  compute='_compute_has_modified_subrequirements',
                                                  store=True)

    @api.model
    def _get_generic_department(self):
        """Get the generic department for evolution projects"""
        return get_generic_department(self.env)

    @api.model
    def default_get(self, fields_list):
        """Set default values for custom requirement lines, ensuring the department is set to generic."""
        defaults = super(ProjectCustomRequirementLine, self).default_get(fields_list)

        # Get context values that may have been set by action_add_custom_requirement_line
        project_id = self.env.context.get('default_project_id')
        project_type = self.env.context.get('default_project_type')
        implementation_category = self.env.context.get('default_implementation_category')

        # Determine if this is an evolution project based on context or project record
        is_evolution = False
        if project_type and implementation_category:
            is_evolution = project_type == 'implementation' and implementation_category == 'evolution'
        elif project_id:
            project = self.env['project.project'].browse(project_id)
            is_evolution = project.project_type == 'implementation' and project.implementation_category == 'evolution'

        # For evolution projects, always use the generic department
        if is_evolution:
            generic_department = self._get_generic_department()
            if generic_department:
                defaults['department_id'] = generic_department.id
        elif 'department_id' in fields_list and 'department_id' not in defaults:
            # Otherwise, only set generic department if not already specified
            generic_department = self._get_generic_department()
            if generic_department:
                defaults['department_id'] = generic_department.id

        return defaults

    @api.depends('department_id')
    def _compute_department_name(self):
        """Set department_name based on the department field for custom requirement lines"""
        for record in self:
            record.department_name = record.department_id.name if record.department_id else False

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
            record.display_name = " - ".join(display_parts) if display_parts else "Ligne d'exigence personnalisée"

    @api.depends('custom_subrequirement_line_ids', 'custom_subrequirement_line_ids.estimated_work_days')
    def _compute_estimated_work_days(self):
        """Sum up working days from all custom subrequirement lines"""
        for record in self:
            record.estimated_work_days = sum(record.custom_subrequirement_line_ids.mapped('estimated_work_days'))

    @api.depends('custom_subrequirement_line_ids')
    def _compute_has_modified_subrequirements(self):
        """Check if any custom subrequirements have been modified from their default values"""
        for record in self:
            record.has_modified_subrequirements = False  # For custom requirements, we don't track modifications

    def action_clear_subrequirement_lines(self):
        """Clear all custom subrequirement lines for the requirement line"""
        self.ensure_one()
        if self.project_stage == 'project' and self.project_type != 'etude_chiffrage':
            raise ValidationError(
                "Vous ne pouvez pas supprimer les sous-exigences d'un projet en phase 'Projet'.")
        if self.custom_subrequirement_line_ids:
            self.custom_subrequirement_line_ids.unlink()
        return True

    def _trim_trailing_spaces(self, vals):
        """
        Trim trailing spaces from name field in vals dict
        """
        # Trim the name field specific to this model
        if vals.get('name'):
            vals['name'] = vals['name'].rstrip()

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create method to ensure proper ordering and validation.
        """
        for vals in vals_list:
            # Trim trailing spaces in name field
            self._trim_trailing_spaces(vals)

            # Get project_id from context if not in vals
            if not vals.get('project_id'):
                project_id = self.env.context.get('default_project_id')
                if project_id:
                    vals['project_id'] = project_id
                else:
                    raise ValidationError("Une ligne d'exigence personnalisée doit être associée à un projet.")

            # If department is not specified, set it to the generic department
            if 'department_id' not in vals:
                vals['department_id'] = self._get_generic_department().id

            # If no order is specified, set next available order specific to custom requirement lines
            if 'order' not in vals and 'project_id' in vals:
                project = self.env['project.project'].browse(vals['project_id'])
                existing_orders = project.custom_requirement_line_ids.mapped('order')
                vals['order'] = max(existing_orders + [0]) + 1

        # Call super to create the records and handle common logic
        return super(ProjectCustomRequirementLine, self).create(vals_list)

    def write(self, vals):
        """
        Override write to trim trailing spaces in name field
        """
        self._trim_trailing_spaces(vals)
        return super(ProjectCustomRequirementLine, self).write(vals)

    def _get_requirement_lines_for_project(self):
        """Return custom requirement lines for the project"""
        return self.env['project.custom.requirement.line'].search([('project_id', '=', self.project_id.id)])

    def _get_concrete_model_name(self):
        """Return the technical name of this model"""
        return 'project.custom.requirement.line'
