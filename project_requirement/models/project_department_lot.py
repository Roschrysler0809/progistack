import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .common_projects import get_generic_department

_logger = logging.getLogger(__name__)


class ProjectDepartmentLot(models.Model):
    _name = 'project.department.lot'
    _description = 'Lot de départements de projet'
    _order = 'lot_number asc'

    name = fields.Char(string='Lot', compute='_compute_name', store=True)
    lot_number = fields.Integer(string='Numéro de lot', required=True, readonly=True)
    project_id = fields.Many2one('project.project', string='Projet', required=True)
    department_ids = fields.Many2many('project.department', string='Départements')
    department_count = fields.Integer(compute='_compute_department_count', string='Nombre de départements')
    department_names = fields.Char(compute='_compute_department_names', string='Départements')
    mep_planned_date = fields.Date(string="Date MEP prévue")
    delivery_planned_date = fields.Date(string="Date Livraison prévue")
    available_department_ids = fields.Many2many('project.department',
                                                compute='_compute_available_department_ids',
                                                string='Départements disponibles')

    @api.depends('lot_number')
    def _compute_name(self):
        for lot in self:
            lot.name = f"Lot {lot.lot_number}"

    @api.depends('department_ids')
    def _compute_department_count(self):
        for lot in self:
            lot.department_count = len(lot.department_ids)

    @api.depends('department_ids')
    def _compute_department_names(self):
        for lot in self:
            lot.department_names = ', '.join(lot.department_ids.mapped('name')) if lot.department_ids else ''

    @api.depends('project_id', 'project_id.department_ids', 'project_id.lot_ids', 'project_id.lot_ids.department_ids',
                 'project_id.implementation_category')
    def _compute_available_department_ids(self):
        """
        Compute departments that are available for selection in this lot:
        - For evolution projects: ONLY include the generic department (plus those already assigned to this lot)
        - For other projects: include all departments EXCEPT the generic department (plus those already assigned to this lot)
        """
        for lot in self:
            if not lot.project_id or not lot.project_id.department_ids:
                lot.available_department_ids = False
                continue

            # Get the generic department 
            generic_department = get_generic_department(self.env)

            # Get all departments assigned to other lots in this project
            other_lots = self.env['project.department.lot'].search([
                ('project_id', '=', lot.project_id.id),
                ('id', '!=', lot.id)
            ])
            assigned_departments = other_lots.mapped('department_ids')

            # Logic is different based on project type
            if lot.project_id.project_type == 'implementation' and lot.project_id.implementation_category == 'evolution':
                # For evolution projects, ONLY the generic department is available (plus those already assigned to this lot)
                if generic_department:
                    # Always include departments already assigned to this lot (so they can be removed if needed)
                    lot.available_department_ids = generic_department | lot.department_ids
                else:
                    lot.available_department_ids = lot.department_ids
            else:
                # For all other projects, all project departments EXCEPT the generic one are available
                project_departments = lot.project_id.department_ids
                if generic_department:
                    project_departments = project_departments.filtered(lambda d: d.id != generic_department.id)

                # Available departments are project departments minus those already assigned to other lots
                # plus those already assigned to this lot (to keep them selectable)
                lot.available_department_ids = (project_departments - assigned_departments) | lot.department_ids

    @api.onchange('department_ids')
    def _onchange_department_ids(self):
        """Update available_department_ids when departments are changed in the form view"""
        if not self.project_id:
            return

        # Get the generic department
        generic_department = get_generic_department(self.env)

        # Get departments assigned to other lots
        other_lots = self.env['project.department.lot'].search([
            ('project_id', '=', self.project_id.id),
            ('id', '!=', self._origin.id)  # Important: use _origin.id to exclude self in DB
        ])
        assigned_departments = other_lots.mapped('department_ids')

        # Logic is different based on project type
        if self.project_id.project_type == 'implementation' and self.project_id.implementation_category == 'evolution':
            # For evolution projects, ONLY the generic department is available (plus those already assigned to this lot)
            if generic_department:
                # Always include departments already assigned to this lot (so they can be removed if needed)
                self.available_department_ids = generic_department | self.department_ids
            else:
                self.available_department_ids = self.department_ids
        else:
            # For all other projects, all project departments EXCEPT the generic one are available
            project_departments = self.project_id.department_ids
            if generic_department:
                project_departments = project_departments.filtered(lambda d: d.id != generic_department.id)

            # Available departments are project departments minus those already assigned to other lots
            # plus those already assigned to this lot (to keep them selectable)
            self.available_department_ids = (project_departments - assigned_departments) | self.department_ids

    @api.constrains('mep_planned_date', 'delivery_planned_date')
    def _check_dates(self):
        """Check that dates are valid in relation to project dates"""
        for lot in self:
            if not lot.project_id:
                continue

            # Get project start date
            project_start_date = lot.project_id.date_start
            if not project_start_date:
                continue

            # Check MEP date
            if lot.mep_planned_date and lot.mep_planned_date < project_start_date:
                raise ValidationError(
                    _("La date de MEP prévue ({}) pour le {} doit être supérieure à la date de début du projet ({})").format(
                        lot.mep_planned_date.strftime('%d/%m/%Y'),
                        lot.name,
                        project_start_date.strftime('%d/%m/%Y')
                    )
                )

            # Check delivery date
            if lot.delivery_planned_date and lot.delivery_planned_date < project_start_date:
                raise ValidationError(
                    _("La date de livraison prévue ({}) pour le {} doit être supérieure à la date de début du projet ({})").format(
                        lot.delivery_planned_date.strftime('%d/%m/%Y'),
                        lot.name,
                        project_start_date.strftime('%d/%m/%Y')
                    )
                )

    @api.constrains('department_ids')
    def _check_department_constraints(self):
        """Constraint method to validate departments immediately when changes are made"""
        for lot in self:
            # Skip validation for unsaved records to avoid blocking date updates
            if isinstance(lot.id, models.NewId):
                continue
            lot._validate_departments()

    def _validate_departments(self):
        """Validate all departments in the lot"""
        for lot in self:
            # Skip validation if requested via context or no project_id
            if not lot.project_id or self.env.context.get('skip_department_validation', False):
                continue

            # Get all departments from other lots in the same project in a single query
            other_lots = self.env['project.department.lot'].search([
                ('project_id', '=', lot.project_id.id),
                ('id', '!=', lot.id)
            ])
            other_departments = other_lots.mapped('department_ids')

            # First validation: Check for departments that are not part of the project
            if lot.project_id and lot.project_id.department_ids:
                invalid_departments = lot.department_ids.filtered(
                    lambda d: d.id not in lot.project_id.department_ids.ids
                )
                if invalid_departments:
                    dept_names = ', '.join(invalid_departments.mapped('name'))
                    raise UserError(f"Les départements suivants ne sont pas associés au projet : {dept_names}")

            # Second validation: Check for departments already used in other lots
            duplicates = lot.department_ids.filtered(lambda d: d in other_departments)
            if duplicates:
                # Get the lot names for better error message
                duplicate_lot_names = []
                for dept in duplicates:
                    lots_with_dept = other_lots.filtered(lambda l: dept in l.department_ids)
                    for l in lots_with_dept:
                        duplicate_lot_names.append(f"{dept.name} (dans {l.name})")

                message = "Les départements suivants sont déjà utilisés dans d'autres lots :\n"
                message += "\n".join(duplicate_lot_names)
                raise UserError(message)

    def action_open_lot_line_form(self):
        """Open the lot form view to edit departments in a popup dialog"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Éditer le {self.name}",
            'res_model': 'project.department.lot',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('project_requirement.view_project_department_lot_form_popup').id,
            'target': 'new',  # Open in a popup dialog
            'context': {
                'form_view_initial_mode': 'edit',  # Start in edit mode
                'default_project_id': self.project_id.id,  # Pass the project ID
                'project_department_ids': self.project_id.department_ids.ids,  # Pass available departments
                'hide_project_id': True,  # Hide the project field in the form
                'skip_department_validation': False,  # Ensure validation runs
            },
        }

    def get_unassigned_departments(self):
        """Get departments that are not yet assigned to any lot in the project"""
        self.ensure_one()

        if not self.project_id:
            return self.env['project.department']

        # Get all departments assigned to lots in this project
        assigned_departments = self.env['project.department.lot'].search([
            ('project_id', '=', self.project_id.id)
        ]).mapped('department_ids')

        # Return departments that are in the project but not assigned to any lot
        return self.project_id.department_ids - assigned_departments

    def _get_next_lot_number(self):
        """Get the next lot number for this project"""
        # Get project_id from context if not in record
        project_id = self.project_id.id if self.project_id else self.env.context.get('default_project_id')
        if not project_id:
            return 1

        # Get the highest lot number for this project
        highest_lot = self.env['project.department.lot'].search([
            ('project_id', '=', project_id)
        ], order='lot_number desc', limit=1)

        return (highest_lot.lot_number + 1) if highest_lot else 1

    def _resequence_lots(self, project):
        """Resequence all lots for a project to ensure consecutive numbering"""
        lots = self.search([('project_id', '=', project.id)], order='lot_number asc')
        for idx, lot in enumerate(lots, 1):
            if lot.lot_number != idx:
                lot.lot_number = idx

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure the lot numbers are assigned correctly when creating new lots"""
        # For each record being created, set the lot_number if not provided
        for vals in vals_list:
            if 'lot_number' not in vals:
                # Create a temporary record to get the project_id context
                temp_record = self.new(vals)
                vals['lot_number'] = temp_record._get_next_lot_number()
        records = super().create(vals_list)

        # After creation, resequence all lots for the affected projects
        projects = records.mapped('project_id')
        for project in projects:
            self._resequence_lots(project)
        return records

    def unlink(self):
        """When deleting lots, store the projects to resequence after deletion"""
        projects = self.mapped('project_id')
        result = super().unlink()
        # Resequence the remaining lots for these projects
        for project in projects:
            self._resequence_lots(project)
        return result
