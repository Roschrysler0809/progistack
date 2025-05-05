from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Project(models.Model):
    _inherit = 'project.project'

    # Project update reference fields
    project_update_count = fields.Integer(compute='_compute_project_update_count', string='Nombre de rapports')
    project_update_ids = fields.One2many('project.update', 'project_id', string='Rapports de projet')

    # Can create update fields
    can_create_update = fields.Boolean(compute='_compute_can_create_update',
                                       string='Peut créer une mise à jour', store=True,
                                       help="Indique si on peut créer une mise à jour pour ce projet")
    update_creation_message = fields.Char(compute='_compute_can_create_update',
                                          string='Message de création de mise à jour', store=True,
                                          help="Message d'information pour la création de mises à jour")

    @api.depends('project_update_ids')
    def _compute_project_update_count(self):
        """Compute the number of project updates."""
        for project in self:
            project.project_update_count = len(project.project_update_ids)

    @api.depends('has_lots', 'all_departments_assigned', 'stage')
    def _compute_can_create_update(self):
        """Compute whether we can create an update for this project."""
        for project in self:
            # Default - can't create updates
            project.can_create_update = False
            project.update_creation_message = False

            # Only implementation projects can have updates
            if project.project_type != 'implementation':
                project.update_creation_message = "Les mises à jour ne sont disponibles que pour les projets d'implémentation."
                continue

            # Project must be in 'project' stage
            if project.stage != 'project':
                project.update_creation_message = "Les mises à jour ne sont disponibles que pour les projets en cours."
                continue

            # Project must have lots
            if not project.has_lots:
                project.update_creation_message = "Vous devez configurer au moins un lot pour créer des mises à jour."
                continue

            # All departments must be assigned to lots
            if not project.all_departments_assigned:
                project.update_creation_message = "Vous devez assigner tous les départements à des lots pour créer des mises à jour."
                continue

            # If all conditions are met, project can have updates
            project.can_create_update = True

    def action_view_project_updates(self):
        """Action to view project updates for this project."""
        self.ensure_one()
        return {
            'name': 'Rapports de projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.update',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
            'target': 'current',
        }

    def action_create_update(self):
        """Create a new update for this project."""
        self.ensure_one()

        # Check if we can create an update
        if not self.can_create_update:
            message = self.update_creation_message or "Impossible de créer une mise à jour pour ce projet."
            raise UserError(message)

        # Open the create update wizard
        return {
            'name': _('Créer une mise à jour de projet'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }

    def get_client_company_name(self):
        """
        Returns the client company name to display in reports.
        If partner is an individual with a parent company, returns the parent company name.
        Otherwise, returns the partner name directly.
        """
        self.ensure_one()
        if not self.partner_id:
            return self.name

        if not self.partner_id.is_company and self.partner_id.parent_id:
            return self.partner_id.parent_id.name
        return self.partner_id.name
