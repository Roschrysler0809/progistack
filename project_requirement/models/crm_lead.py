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
        """Create a project from the CRM lead or update an existing one"""
        self.ensure_one()

        # Validate next_step is selected
        if not self.next_step:
            raise models.ValidationError("Veuillez sélectionner une prochaine étape avant de créer un projet.")

        project_type = convert_next_step_to_project_type(self.next_step)

        # Vérifier si un projet existe déjà lié à cette opportunité
        existing_project = self.project_id

        if existing_project:
            # Si le projet existe déjà, ouvrez-le simplement sans mise à jour
            # pour éviter les problèmes avec les départements obligatoires
            project_id = existing_project.id
        else:
            # Créer un nouveau projet
            vals = {
                'name': self.name,
                'partner_id': self.partner_id.id,
                'project_type': project_type,
                'stage': 'preparation',
                'from_crm': True,
            }

            # Set department_type and implementation_category only if next_step is implementation
            if self.next_step == 'implementation':
                vals.update({
                    'department_type': self.department_type,
                    'implementation_category': self.implementation_category,
                })

                # Si c'est un projet d'évolution, nous devons ajouter un département générique
                if self.implementation_category == 'evolution':
                    # Utiliser la fonction get_generic_department du module common_projects
                    generic_dept = get_generic_department(self.env)
                    vals['department_ids'] = [(4, generic_dept.id)]

            # Set etude_chiffrage_category only if next_step is etude_chiffrage
            if self.next_step == 'etude_chiffrage':
                vals['etude_chiffrage_category'] = self.etude_chiffrage_category

            # Create the project
            project = self.env['project.project'].create(vals)

            # Link the project to the lead
            self.project_id = project.id
            project_id = project.id

        # Open the project
        return {
            'name': 'Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': project_id,
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
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
