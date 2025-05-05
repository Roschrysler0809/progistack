from odoo import api, fields, models, _
from ...project_requirement.models.common_dates import (
    get_monday_of_week
)


class ProjectUpdateWizard(models.TransientModel):
    _name = 'project.update.wizard'
    _description = 'Assistant de création de mise à jour de projet'

    project_id = fields.Many2one('project.project', string='Projet', required=True)
    report_date = fields.Datetime(string='Date de début du rapport', required=True,
                                  default=lambda self: fields.Datetime.from_string(
                                      get_monday_of_week(fields.Date.today())),
                                  help='Date de début du rapport')
    report_date_end = fields.Datetime(string='Date de fin du rapport',
                                      help='Date de fin du rapport')
    department_ids = fields.Many2many(related='project_id.department_ids', string='Départements', readonly=True)

    # Fields for copying data from previous update
    copy_previous_data = fields.Boolean(string='Copier depuis mise à jour précédente', default=True,
                                        help='Copier les données de la mise à jour précédente')
    last_update_id = fields.Many2one('project.update', string='Dernière mise à jour',
                                     compute='_compute_last_update_id', store=False)
    has_previous_update = fields.Boolean(string='A une mise à jour précédente',
                                         compute='_compute_last_update_id', store=False)

    @api.depends('project_id')
    def _compute_last_update_id(self):
        """Find the most recent update for this project if any."""
        for wizard in self:
            last_update = False
            if wizard.project_id:
                last_update = self.env['project.update'].search([
                    ('project_id', '=', wizard.project_id.id)
                ], order='report_date desc, id desc', limit=1)

            wizard.last_update_id = last_update
            wizard.has_previous_update = bool(last_update)

            # If there's no previous update, force copy_previous_data to False
            if not last_update:
                wizard.copy_previous_data = False

    def action_create_update(self):
        """Create a project update with the wizard data."""
        self.ensure_one()

        # Create the project update
        vals = {
            'project_id': self.project_id.id,
            'report_date': self.report_date,
            'custom_status': 'sunny',  # Default status
            'progress': 0,  # Default progress
            'user_id': self.env.user.id,
            'description': '',  # Empty description
        }
        if self.report_date_end:
            vals['report_date_end'] = self.report_date_end

        # Pass context to prevent project.update.create from running line logic again
        project_update = self.env['project.update'].with_context(wizard_creating_update=True).create(vals)

        # Determine the last update to potentially copy from for tracking lines
        last_update_for_tracking = self.last_update_id if self.copy_previous_data else None

        # Call the generation methods on the newly created update
        project_update.generate_flash_lines()
        project_update.generate_tracking_lines(last_update=last_update_for_tracking)

        # Open the created update in form view
        return {
            'name': _('Mise à jour du projet'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.update',
            'res_id': project_update.id,
            'view_mode': 'form',
            'target': 'current',
        }
