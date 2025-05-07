from odoo import models, fields, api
from .common_projects import (
    DEPARTMENT_TYPE_SELECTION,
    IMPLEMENTATION_CATEGORY_SELECTION,
    ETUDE_CHIFFRAGE_CATEGORY_SELECTION,
    PROJECT_TYPE_NEXT_STEP_SELECTION,
    convert_next_step_to_project_type
)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Project fields
    next_step = fields.Selection(PROJECT_TYPE_NEXT_STEP_SELECTION, string="Prochaine étape")
    department_type = fields.Selection(DEPARTMENT_TYPE_SELECTION, string="Suivi département")
    implementation_category = fields.Selection(IMPLEMENTATION_CATEGORY_SELECTION, string="Catégorie")
    etude_chiffrage_category = fields.Selection(ETUDE_CHIFFRAGE_CATEGORY_SELECTION, string="Catégorie")
    project_id = fields.Many2one('project.project', string="Projet", readonly=True)

    # Computed field to determine if this is an evolution project
    is_next_step_evolution = fields.Boolean(compute='_compute_is_next_step_evolution',
                                            string="Prochaine étape est évolution", store=True)

    @api.depends('next_step', 'implementation_category')
    def _compute_is_next_step_evolution(self):
        """Compute whether the next step is an evolution implementation project"""
        for lead in self:
            lead.is_next_step_evolution = (lead.next_step == 'implementation' and
                                           lead.implementation_category == 'evolution')

    @api.onchange('next_step')
    def _onchange_next_step(self):
        """Automatically set categories based on the selected next_step"""
        if self.next_step == 'implementation':
            # Clear other project type fields
            self.etude_chiffrage_category = False
            # Set default values
            self.implementation_category = 'integration'
            self.department_type = False
            # Don't set department_type - user must select this manually
        elif self.next_step == 'etude_chiffrage':
            # Clear other project type fields
            self.implementation_category = False
            self.department_type = False
            # Set default values
            self.etude_chiffrage_category = 'billable'

    @api.onchange('implementation_category')
    def _onchange_implementation_category(self):
        """Handle changes to implementation category"""
        if self.next_step == 'implementation':
            if self.implementation_category == 'evolution':
                # For evolution category, force department_type to standard
                self.department_type = 'standard'
            else:
                # When changing from evolution to something else, reset department_type so user must select manually
                self.department_type = False

    def action_create_project(self):
        """Create a project from the CRM lead"""
        self.ensure_one()

        # Validate next_step is selected
        if not self.next_step:
            raise models.ValidationError("Veuillez sélectionner une prochaine étape avant de créer un projet.")

        project_type = convert_next_step_to_project_type(self.next_step)

        # Set department_type and implementation_category only if next_step is implementation
        department_type = self.department_type if self.next_step == 'implementation' else False
        implementation_category = self.implementation_category if self.next_step == 'implementation' else False

        # Set etude_chiffrage_category only if next_step is etude_chiffrage
        etude_chiffrage_category = self.etude_chiffrage_category if self.next_step == 'etude_chiffrage' else False
        # Open the project form view with default values
        return {
            'name': 'Nouveau Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': self.name,
                'default_partner_id': self.partner_id.id,
                'default_project_type': project_type,
                'default_department_type': department_type,
                'default_implementation_category': implementation_category,
                'default_etude_chiffrage_category': etude_chiffrage_category,
                'default_stage': 'preparation',
                'default_from_crm': True,
                'form_view_initial_mode': 'edit',
                'crm_lead_id': self.id,
            },
        }

    def action_view_project(self):
        """Open the project linked to this lead"""
        self.ensure_one()

        if not self.project_id:
            return {
                'type': 'ir.actions.act_window_close'
            }

        return {
            'name': 'Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }
