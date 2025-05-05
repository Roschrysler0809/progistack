from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProjectRequirementLine(models.Model):
    """
    This model represents a requirement line in a project.
    Each requirement line belongs to a project and is linked to a requirement.
    It can contain multiple subrequirement lines.
    Requirements are organized by order which determines their planned start and end dates.
    """
    _name = 'project.requirement.line'
    _inherit = 'project.abstract.requirement.line'
    _description = "Ligne d'exigence du projet"
    _order = 'order, planned_end_date, requirement_id, id'
    _rec_name = 'display_name'

    # Fields specific to standard requirement lines
    description = fields.Text(string="Description", help="Description personnalisée de l'exigence")
    requirement_id = fields.Many2one('project.requirement', string="Exigence", required=True)
    project_department_ids = fields.Many2many(related='project_id.department_ids', string='Project Departments',
                                              readonly=True)
    implementation_project_id = fields.Many2one(related='project_id.implementation_project_id',
                                                string="Projet d'implémentation", readonly=True)
    type = fields.Selection(related='requirement_id.type', string="Type", readonly=True, store=True)
    department_id = fields.Many2one(related='requirement_id.department_id', string="Département", readonly=True,
                                    store=True)
    department_name = fields.Char(related='department_id.name', string="Nom du département", readonly=True, store=True)
    requirement_name = fields.Char(related='requirement_id.name', string="Nom de l'exigence", readonly=True, store=True)
    sequence = fields.Integer(related='requirement_id.sequence', string="Séquence", readonly=True, store=True)
    estimated_work_days = fields.Float(string="Charge (Jours)", compute='_compute_estimated_work_days',
                                       store=True, readonly=True,
                                       help="Nombre de jours ouvrés estimés pour cette exigence")
    is_modified = fields.Boolean(string="Modifié", default=False, help="Indique si l'exigence a été modifiée")
    subrequirement_line_ids = fields.One2many('project.subrequirement.line', 'requirement_line_id',
                                              string="Lignes de sous-exigences",
                                              domain="[('subrequirement_id.project_type', '!=', 'etude_chiffrage')]")
    preserve_subrequirements = fields.Boolean(
        string="Conserver les sous-exigences",
        compute='_compute_preserve_subrequirements',
        help="Si coché, les modifications apportées aux sous-exigences seront conservées lors du changement d'exigence"
    )

    def name_get(self):
        """Override name_get to use the computed display_name field"""
        return [(record.id, record.display_name) for record in self]

    @api.depends('department_id', 'requirement_id', 'description')
    def _compute_display_name(self):
        """Compute display name based on department, requirement and description"""
        for record in self:
            if record.requirement_id:
                display_parts = []

                # Always include the department if available
                if record.department_id:
                    display_parts.append(record.department_id.name)

                # Add the requirement name
                if record.requirement_id:
                    display_parts.append(record.requirement_id.name)

                # Create the display name with parts joined by a separator
                record.display_name = " - ".join(display_parts)
            else:
                record.display_name = "Ligne d'exigence"

    @api.depends('requirement_id')
    def _compute_description(self):
        """
        When the requirement changes, clear the description.
        The description will only be set when explicitly requested via the UI.
        """
        for record in self:
            # Clear description when requirement changes
            if record.requirement_id and record._origin.requirement_id and record.requirement_id != record._origin.requirement_id:
                record.description = False

    @api.depends('subrequirement_line_ids', 'subrequirement_line_ids.estimated_work_days')
    def _compute_estimated_work_days(self):
        """Sum up working days from all subrequirement lines"""
        for record in self:
            record.estimated_work_days = sum(record.subrequirement_line_ids.mapped('estimated_work_days'))

    @api.depends('subrequirement_line_ids.is_modified')
    def _compute_has_modified_subrequirements(self):
        """Check if any subrequirements have been modified from their default values"""
        for record in self:
            record.has_modified_subrequirements = any(line.is_modified for line in record.subrequirement_line_ids)

    @api.depends('has_modified_subrequirements')
    def _compute_preserve_subrequirements(self):
        """Compute whether to preserve subrequirements based on modifications and context"""
        for record in self:
            # If there are no modified subrequirements, we don't need to preserve
            if not record.has_modified_subrequirements:
                record.preserve_subrequirements = False
                continue

            # If we're changing the requirement (from context), don't preserve
            if self.env.context.get('changing_requirement'):
                record.preserve_subrequirements = False
                continue

            # Default to preserving if there are modifications
            record.preserve_subrequirements = True

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """When project changes, update domain for requirement selection"""
        if self.project_id:
            # Clear requirement when project changes
            self.requirement_id = False

            # Force refresh of project_department_ids field to ensure it's available for domain filtering
            if self.project_id.department_ids:
                self.project_department_ids = self.project_id.department_ids

        return {}

    @api.onchange('requirement_id')
    def _onchange_requirement_id(self):
        """
        Update subrequirements when requirement changes.
        This only triggers when manually changing a requirement in the UI.
        """
        # Keep track of the requirement that was just selected
        new_requirement_id = self.requirement_id.id if self.requirement_id else False

        # Always clear and recreate subrequirements when changing requirement
        self.subrequirement_line_ids = [(5, 0, 0)]  # Command 5: Delete all

        if self.requirement_id:
            # Get all subrequirements for the selected requirement, excluding 'etude_chiffrage' type
            subrequirements = self.requirement_id.subrequirement_ids.filtered(
                lambda s: s.project_type != 'etude_chiffrage'
            )

            # Only proceed if there are subrequirements to add
            if subrequirements:
                # Add all subrequirements in a single operation
                values = []
                for subreq in subrequirements:
                    values.append((0, 0, {
                        'subrequirement_id': subreq.id,
                        'complexity': subreq.complexity,
                        'estimated_work_days': subreq.estimated_work_days,
                    }))

                # Add all new subrequirements at once
                if values:
                    self.subrequirement_line_ids = values

        # Force recomputation of dates and other computed fields
        self.invalidate_recordset(['planned_start_date', 'planned_end_date'])

        # Return empty dict to keep form in edit mode
        return {}

    def action_clear_subrequirement_lines(self):
        """Clear all subrequirement lines for the requirement line"""
        self.ensure_one()

        # Don't allow clearing subrequirements for projects in 'project' stage except etude_chiffrage without implementation
        if self.project_stage == 'project' and (
                self.project_type != 'etude_chiffrage' or self.project_id.implementation_project_id):
            raise ValidationError(
                "Vous ne pouvez pas supprimer les sous-exigences d'un projet en phase 'Projet'.")

        if self.subrequirement_line_ids:
            self.subrequirement_line_ids.unlink()
        return True

    def _get_requirement_lines_for_project(self):
        """Return requirement lines for the project"""
        return self.env['project.requirement.line'].search([('project_id', '=', self.project_id.id)])

    def _get_concrete_model_name(self):
        """Return the technical name of this model"""
        return 'project.requirement.line'

    def _trim_trailing_spaces(self, vals):
        """
        Trim trailing spaces from description field in vals dict
        """
        # Then trim the description field specific to this model
        if vals.get('description'):
            vals['description'] = vals['description'].rstrip()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to automatically add subrequirement lines when creating requirement lines.
        """
        # Trim trailing spaces in description field
        for vals in vals_list:
            self._trim_trailing_spaces(vals)

        result = super(ProjectRequirementLine, self).create(vals_list)

        # Skip auto-subrequirements if context flag is set
        if self.env.context.get('skip_auto_subrequirements'):
            return result

        # For each created requirement line, create its subrequirements
        for record in result:
            if record.requirement_id:
                # Get all subrequirements for the selected requirement, excluding 'etude_chiffrage' type
                subrequirements = record.requirement_id.subrequirement_ids.filtered(
                    lambda s: s.project_type != 'etude_chiffrage'
                )

                # Only proceed if there are subrequirements to add and none exist yet
                if subrequirements and not record.subrequirement_line_ids:
                    # Add all subrequirements in a single operation
                    values = []
                    for subreq in subrequirements:
                        values.append((0, 0, {
                            'subrequirement_id': subreq.id,
                            'complexity': subreq.complexity,
                            'estimated_work_days': subreq.estimated_work_days,
                        }))

                    # Add all new subrequirements at once
                    if values:
                        record.subrequirement_line_ids = values

        return result

    def write(self, vals):
        """
        Override write to trim trailing spaces in description field
        """
        self._trim_trailing_spaces(vals)
        return super(ProjectRequirementLine, self).write(vals)
