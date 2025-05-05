import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ProjectSubrequirementLine(models.Model):
    """
    This model represents a subrequirement line in a project requirement line.
    Each subrequirement line belongs to a requirement line and is linked to a subrequirement.
    """
    _name = 'project.subrequirement.line'
    _inherit = ['project.abstract.subrequirement.line']
    _description = "Ligne de sous-exigence du projet"
    _order = 'requirement_line_id, order, id'

    # Specific fields for standard subrequirement lines
    requirement_line_id = fields.Many2one('project.requirement.line', string="Ligne d'exigence",
                                          required=True, ondelete='cascade')
    project_stage = fields.Selection(related='requirement_line_id.project_id.stage', string="Étape du projet",
                                     store=True)
    subrequirement_id = fields.Many2one('project.subrequirement', string="Sous-exigence", required=True,
                                        domain="[('project_type', '!=', 'etude_chiffrage')]")
    department_id = fields.Many2one('project.department', string="Département", store=True, readonly=True)
    subrequirement_type = fields.Selection(related='subrequirement_id.subrequirement_type',
                                           string="Type de sous-exigence", readonly=True, store=True)
    project_type = fields.Selection(related='subrequirement_id.project_type',
                                    string="Type de projet", readonly=True, store=True)
    parent_project_type = fields.Selection(related='requirement_line_id.project_id.project_type',
                                           string="Type de projet parent", readonly=True)
    parent_implementation_project_id = fields.Many2one(
        related='requirement_line_id.project_id.implementation_project_id', string="Projet d'implémentation parent",
        readonly=True)
    is_modified = fields.Boolean(string="Modifié", compute='_compute_is_modified', store=True)

    @api.depends('department_id', 'subrequirement_id')
    def _compute_display_name(self):
        """Compute display name based on department and subrequirement"""
        for record in self:
            if record.department_id and record.subrequirement_id:
                record.display_name = f"[{record.department_id.name}] {record.subrequirement_id.description}"
            elif record.subrequirement_id:
                record.display_name = f"{record.subrequirement_id.description}"
            elif record.department_id:
                record.display_name = f"[{record.department_id.name}]"
            else:
                record.display_name = "Ligne de sous-exigence"

    @api.depends('subrequirement_id', 'subrequirement_id.department_id')
    def _compute_department_id(self):
        """Compute department_id based on subrequirement department"""
        for record in self:
            if record.subrequirement_id and record.subrequirement_id.department_id:
                record.department_id = record.subrequirement_id.department_id.id
            else:
                record.department_id = False

    @api.depends('estimated_work_days', 'subrequirement_id.estimated_work_days')
    def _compute_is_modified(self):
        """Compute if estimated days have been modified from original value"""
        for record in self:
            record.is_modified = record.estimated_work_days != record.subrequirement_id.estimated_work_days

    @api.onchange('subrequirement_id')
    def _onchange_subrequirement_id_department(self):
        """Update department_id when subrequirement_id changes"""
        if self.subrequirement_id and self.subrequirement_id.department_id:
            self.department_id = self.subrequirement_id.department_id.id

    @api.onchange('subrequirement_id', 'estimated_work_days')
    def _onchange_subrequirement_id(self):
        """
        When subrequirement or estimated days change:
        1. For new records, set initial estimated days from subrequirement
        2. For existing records, only update complexity if estimated_work_days changed
        3. Trigger recomputation of parent requirement line fields only if estimated_work_days changed
        """
        # For new records, set estimated days from subrequirement
        if self.subrequirement_id and not self._origin.id:
            # Only set if no value was provided
            # Note: Important check to make sure it doesn't get overridden by the default value
            if not self.estimated_work_days:
                self.estimated_work_days = self.subrequirement_id.estimated_work_days

        # For existing records, only update if estimated_work_days changed
        elif self._origin.id and self.estimated_work_days != self._origin.estimated_work_days:
            # Force recomputation of parent requirement line fields
            if self.requirement_line_id:
                self._update_parent_requirement_line()
                self.requirement_line_id._compute_has_modified_subrequirements()

    def action_revert_estimated_work_days(self):
        """Revert estimated days to the original value from the referenced subrequirement"""
        for record in self:
            # Don't allow reverting for projects in 'project' stage except etude_chiffrage without implementation
            project = record.requirement_line_id.project_id
            if (project.stage == 'project' and
                    (project.project_type != 'etude_chiffrage' or project.implementation_project_id)):
                raise ValidationError(
                    "Vous ne pouvez pas modifier les sous-exigences d'un projet en phase 'Projet'.")

            if record.subrequirement_id:
                # Use skip_date_validation context to prevent validation errors during the update
                record.with_context(skip_date_validation=True).write({
                    'estimated_work_days': record.subrequirement_id.estimated_work_days
                })
        return True

    def open_form(self):
        """Opens the subrequirement line form view."""
        self.ensure_one()

        # Check if the project is in project stage and not an etude_chiffrage project
        if self.project_stage == 'project' and self.parent_project_type != 'etude_chiffrage':
            raise UserError(_("Impossible de modifier une ligne de sous-exigence en phase projet."))

        return {
            'name': _('Modifier la ligne de sous-exigence'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.subrequirement.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }

    def _trim_trailing_spaces(self, vals):
        """
        Trim trailing spaces from any description field in vals dict
        """
        # We don't have a direct description field to trim, but if the subrequirement model has one,
        # we could trim it here when needed.
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle new subrequirements and ensure requirement_id is set properly"""
        for vals in vals_list:
            # Trim trailing spaces if needed
            self._trim_trailing_spaces(vals)

            # If a subrequirement is being created on the fly (inline creation)
            if vals.get('subrequirement_id') and isinstance(vals['subrequirement_id'], dict):
                # Get the requirement line to retrieve requirement_id
                if vals.get('requirement_line_id'):
                    req_line = self.env['project.requirement.line'].browse(vals['requirement_line_id'])
                    if req_line and req_line.requirement_id:
                        # Add requirement_id to the subrequirement values
                        vals['subrequirement_id']['requirement_id'] = req_line.requirement_id.id

                        # Set project_type from context if not explicitly provided
                        if not vals['subrequirement_id'].get('project_type'):
                            vals['subrequirement_id']['project_type'] = self.env.context.get('default_project_type',
                                                                                             'implementation')

        # Create all records in batch
        result = super(ProjectSubrequirementLine, self).create(vals_list)

        # Set department_id and estimated_work_days from subrequirement if needed
        for record in result:
            # Always set department_id from subrequirement
            if record.subrequirement_id and record.subrequirement_id.department_id:
                record.write({'department_id': record.subrequirement_id.department_id.id})

            # If no estimated_work_days was set, initialize from subrequirement
            vals = next((v for v in vals_list if v.get('requirement_line_id') == record.requirement_line_id.id and
                         v.get('subrequirement_id') == record.subrequirement_id.id), {})
            if not vals.get(
                    'estimated_work_days') and record.subrequirement_id and record.subrequirement_id.estimated_work_days:
                record.write({'estimated_work_days': record.subrequirement_id.estimated_work_days})

        return result

    def write(self, values):
        """
        Override write to update parent requirement line and project dates when estimated days change.
        Uses Odoo 18's notification system for safer field recomputation.
        """
        # Trim trailing spaces if needed
        self._trim_trailing_spaces(values)

        # Store the requirement_line_ids before the update to detect changes
        old_req_lines = self.mapped('requirement_line_id')

        # Execute the standard update
        result = super().write(values)

        # Get the updated requirement lines
        current_req_lines = self.mapped('requirement_line_id')

        # Combination of old and new requirement lines that might need updating
        req_lines_to_update = old_req_lines | current_req_lines

        # Only trigger recomputation if estimated_work_days changed or requirement line changed
        if 'estimated_work_days' in values or old_req_lines != current_req_lines:
            # Store affected requirement lines and projects before any operations
            req_lines = req_lines_to_update.exists()

            # First update the immediate parent requirement lines
            if req_lines:
                # Use a try-except block to handle any errors during recomputation
                try:
                    # Force update of is_modified
                    for record in self:
                        record._compute_is_modified()

                    # Safely update working days on parent requirement lines
                    req_lines._compute_estimated_work_days()

                    # Get all project requirement lines that need updating
                    projects = req_lines.mapped('project_id').exists()
                    if projects:
                        # Find all requirement lines in these projects
                        all_project_lines = self.env['project.requirement.line'].search([
                            ('project_id', 'in', projects.ids)
                        ])

                        if all_project_lines:
                            # First, force compute on the specific lines we modified
                            for req_line in req_lines:
                                req_line.with_context(skip_date_validation=True)._compute_planned_dates()
                                req_line.with_context(skip_date_validation=True)._compute_estimated_days()

                            # Then recompute all lines in the project for consistency (dates depend on each other)
                            all_project_lines.with_context(skip_date_validation=True)._compute_planned_dates()
                            all_project_lines.with_context(skip_date_validation=True)._compute_estimated_days()

                            # Force an immediate UI update by committing the transaction
                            self.env.cr.commit()

                except Exception as e:
                    # Log the error but don't raise it to prevent transaction rollback
                    logging.error(f"Error during recomputation: {str(e)}")

        return result

    def _get_concrete_model_name(self):
        """Return the technical name of this model"""
        return 'project.subrequirement.line'

    def _get_parent_requirement_field_name(self):
        """Return the field name that points to the parent requirement line"""
        return 'requirement_line_id'
