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
    project_id = fields.Many2one('project.project', string='Projet', required=True, ondelete='cascade')
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
        - For other projects: include all departments EXCEPT the generic department and 'transverse' department 
          (plus those already assigned to this lot)
        """
        for lot in self:
            if not lot.project_id or not lot.project_id.department_ids:
                lot.available_department_ids = lot.env['project.department'].browse([])
                continue

            generic_department = get_generic_department(self.env)
            
            other_lots = self.env['project.department.lot'].search([
                ('project_id', '=', lot.project_id.id),
                ('id', '!=', lot.id)
            ])
            assigned_departments_to_other_lots = other_lots.mapped('department_ids')

            if lot.project_id.project_type == 'implementation' and lot.project_id.implementation_category == 'evolution':
                # For evolution projects, ONLY the generic department is available (plus those already assigned to this lot)
                # This inherently excludes 'transverse' unless it is the generic or already in the lot.
                lot.available_department_ids = (generic_department if generic_department else self.env['project.department']) | lot.department_ids
            else:
                # For all other projects
                selectable_departments = lot.project_id.department_ids

                # Exclude generic department
                if generic_department:
                    selectable_departments = selectable_departments.filtered(lambda d: d.id != generic_department.id)
                
                # Exclude 'transverse' department
                transverse_department_record = self.env['project.department'].search([('code', '=', 'transverse')], limit=1)
                if transverse_department_record:
                    selectable_departments = selectable_departments.filtered(lambda d: d.id != transverse_department_record.id)

                # Available departments are:
                # (Project's selectable departments (minus generic, minus transverse))
                # MINUS (Departments assigned to other lots)
                # UNION (Departments already assigned to this current lot - to allow removal)
                lot.available_department_ids = (selectable_departments - assigned_departments_to_other_lots) | lot.department_ids

    @api.onchange('department_ids')
    def _onchange_department_ids(self):
        """Update available_department_ids when departments are changed in the form view"""
        if not self.project_id:
            self.available_department_ids = self.env['project.department'].browse([])
            return

        generic_department = get_generic_department(self.env)
        
        other_lots_domain = [('project_id', '=', self.project_id.id)]
        if self._origin and self._origin.id: # Check if the record is already saved
             other_lots_domain.append(('id', '!=', self._origin.id))
        other_lots = self.env['project.department.lot'].search(other_lots_domain)
        assigned_departments_to_other_lots = other_lots.mapped('department_ids')

        if self.project_id.project_type == 'implementation' and self.project_id.implementation_category == 'evolution':
            # For evolution projects, ONLY the generic department is available (plus those already assigned to this lot)
            # This inherently excludes 'transverse' unless it is the generic or already in the lot.
            self.available_department_ids = (generic_department if generic_department else self.env['project.department']) | self.department_ids
        else:
            # For all other projects
            selectable_departments = self.project_id.department_ids

            # Exclude generic department
            if generic_department:
                selectable_departments = selectable_departments.filtered(lambda d: d.id != generic_department.id)
            
            # Exclude 'transverse' department
            transverse_department_record = self.env['project.department'].search([('code', '=', 'transverse')], limit=1)
            if transverse_department_record:
                selectable_departments = selectable_departments.filtered(lambda d: d.id != transverse_department_record.id)

            # Available departments are:
            # (Project's selectable departments (minus generic, minus transverse))
            # MINUS (Departments assigned to other lots)
            # UNION (Departments already assigned to this current lot - to allow removal)
            self.available_department_ids = (selectable_departments - assigned_departments_to_other_lots) | self.department_ids

    @api.constrains('mep_planned_date', 'delivery_planned_date')
    def _check_dates(self):
        """Check that dates are valid in relation to project dates"""
        for lot in self:
            if not lot.project_id:
                continue

            project_start_date = lot.project_id.date_start
            if not project_start_date:
                continue

            if lot.mep_planned_date and lot.mep_planned_date < project_start_date:
                raise ValidationError(
                    _("La date de MEP prévue ({}) pour le {} doit être supérieure à la date de début du projet ({})").format(
                        lot.mep_planned_date.strftime('%d/%m/%Y'),
                        lot.name,
                        project_start_date.strftime('%d/%m/%Y')
                    )
                )

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
            if isinstance(lot.id, models.NewId):
                continue
            lot._validate_departments()

    def _validate_departments(self):
        """Validate all departments in the lot"""
        for lot in self:
            if not lot.project_id or self.env.context.get('skip_department_validation', False):
                continue

            other_lots = self.env['project.department.lot'].search([
                ('project_id', '=', lot.project_id.id),
                ('id', '!=', lot.id)
            ])
            other_departments = other_lots.mapped('department_ids')

            if lot.project_id and lot.project_id.department_ids:
                invalid_departments = lot.department_ids.filtered(
                    lambda d: d.id not in lot.project_id.department_ids.ids
                )
                if invalid_departments:
                    dept_names = ', '.join(invalid_departments.mapped('name'))
                    raise UserError(f"Les départements suivants ne sont pas associés au projet : {dept_names}")

            duplicates = lot.department_ids.filtered(lambda d: d in other_departments)
            # We don't check for 'transverse' duplicates here specifically, 
            # as it should ideally not be selectable for multiple lots unless it was the generic one in an evolution project.
            # The main logic for availability handles the 'transverse' department.
            if duplicates:
                duplicate_lot_names = []
                for dept in duplicates:
                    lots_with_dept = other_lots.filtered(lambda l: dept in l.department_ids)
                    for l_item in lots_with_dept: # Renamed l to l_item to avoid conflict with lambda d
                        duplicate_lot_names.append(f"{dept.name} (dans {l_item.name})")

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
            'target': 'new',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_project_id': self.project_id.id,
                # 'project_department_ids': self.project_id.department_ids.ids, # This might be overridden by available_department_ids logic
                'hide_project_id': True,
                'skip_department_validation': False,
            },
        }

    def get_unassigned_departments(self):
        """Get departments that are not yet assigned to any lot in the project"""
        self.ensure_one()

        if not self.project_id:
            return self.env['project.department']

        assigned_departments_in_project = self.env['project.department.lot'].search([
            ('project_id', '=', self.project_id.id)
        ]).mapped('department_ids')
        
        # Also consider filtering out 'transverse' and 'generic' if they should not be listed as "unassigned" for new lots.
        # For now, follows existing logic of project_id.department_ids - assigned_departments_in_project
        unassigned = self.project_id.department_ids - assigned_departments_in_project
        
        # Further exclude transverse and generic from being suggested as "unassigned"
        # unless specific project logic (e.g. evolution project for generic) demands it.
        # This part might need refinement based on how "get_unassigned_departments" is used.
        # For now, we'll ensure 'transverse' is not in this list.
        generic_department = get_generic_department(self.env)
        transverse_department_record = self.env['project.department'].search([('code', '=', 'transverse')], limit=1)
        
        departments_to_exclude = self.env['project.department']
        if transverse_department_record:
            departments_to_exclude |= transverse_department_record
        # Depending on usage, you might want to exclude generic_department too, unless it's an evolution project scenario
        # if generic_department and not (self.project_id.project_type == 'implementation' and self.project_id.implementation_category == 'evolution'):
        #    departments_to_exclude |= generic_department

        return unassigned - departments_to_exclude


    def _get_next_lot_number(self):
        """Get the next lot number for this project"""
        project_id = self.project_id.id if self.project_id else self.env.context.get('default_project_id')
        if not project_id:
            return 1

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
        for vals in vals_list:
            if 'lot_number' not in vals:
                temp_record = self.new(vals) # Create a temporary record to get context (like project_id)
                vals['lot_number'] = temp_record._get_next_lot_number()
        records = super().create(vals_list)

        projects = records.mapped('project_id')
        for project in projects:
            self._resequence_lots(project)
        return records

    def unlink(self):
        """When deleting lots, store the projects to resequence after deletion"""
        projects = self.mapped('project_id')
        result = super().unlink()
        for project in projects:
            self._resequence_lots(project)
        return result