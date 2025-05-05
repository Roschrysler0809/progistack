from odoo import models, fields, api
from odoo.exceptions import ValidationError
from .common_requirements import COMPLEXITY_SELECTION, PROJECT_TYPE_SELECTION, SUBREQUIREMENT_TYPE_SELECTION
from .common_requirements import get_complexity_from_days


class ProjectSubrequirement(models.Model):
    _name = 'project.subrequirement'
    _description = 'Sous-exigence'
    _rec_name = 'description'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=1)
    description = fields.Text(string="Description", required=True)
    requirement_id = fields.Many2one('project.requirement', string="Exigence", required=True, ondelete='cascade',
                                     index=True, default=lambda self: self.env.context.get('default_requirement_id'))
    department_id = fields.Many2one('project.department', string="Département",
                                    related='requirement_id.department_id',
                                    store=True, index=True, readonly=True)
    complexity = fields.Selection(COMPLEXITY_SELECTION, string="Complexité",
                                  compute='_compute_complexity', store=True, readonly=True)
    estimated_work_days = fields.Float(string="Charge (Jours)", default=0, store=True)
    subrequirement_type = fields.Selection(SUBREQUIREMENT_TYPE_SELECTION, string="Type de sous-exigence",
                                           default='externe', required=True)
    project_type = fields.Selection(PROJECT_TYPE_SELECTION, string="Type de projet", required=True)

    @api.depends('estimated_work_days')
    def _compute_complexity(self):
        for record in self:
            record.complexity = get_complexity_from_days(record.estimated_work_days)

    @api.constrains('estimated_work_days')
    def _check_estimated_work_days(self):
        """Validate that estimated days are not negative"""
        for record in self:
            if record.estimated_work_days < 0:
                raise ValidationError("La charge (Jours) ne peut pas être négative.")

    def write(self, vals):
        """Override write to ensure the computed fields on related models are updated"""
        result = super(ProjectSubrequirement, self).write(vals)

        # If estimated_work_days changed, manually trigger recomputation on related requirements
        if 'estimated_work_days' in vals:
            # Force recompute the estimated_work_days field on the requirement
            if self.requirement_id:
                self.requirement_id._compute_estimated_work_days()

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure requirement_id is set"""
        for vals in vals_list:
            # If creating from a requirement form, ensure requirement_id is set
            if not vals.get('requirement_id'):
                if self.env.context.get('default_requirement_id'):
                    vals['requirement_id'] = self.env.context.get('default_requirement_id')
                # Skip the validation during import (load) operations
                elif not self.env.context.get('import_file'):
                    # Provide fallback to ensure requirement_id is always set except for imports
                    raise ValueError("Le champ 'requirement_id' est obligatoire pour les sous-exigences")

        return super(ProjectSubrequirement, self).create(vals_list)

    @api.model
    def load(self, fields, data):
        """Override load method to handle imports with proper requirement-department matching"""
        if 'requirement_id' in fields and 'department_id' in fields:
            # Get the indices for requirement and department fields
            req_idx = fields.index('requirement_id')
            dept_idx = fields.index('department_id')

            # Pre-load all departments for efficient lookups
            all_departments = {dept.name: dept.id for dept in self.env['project.department'].search([])}

            # Pre-load all requirements with their departments for efficient matching
            # This creates a mapping from (name, department_id) to requirement_id
            all_requirements = {}
            for req in self.env['project.requirement'].search([]):
                key = (req.name, req.department_id.id)
                all_requirements[key] = req.id

            # Process each row
            for row in data:
                # Get requirement name and department from the row
                req_name = row[req_idx] if isinstance(row[req_idx], str) else str(row[req_idx])
                dept_name = row[dept_idx] if isinstance(row[dept_idx], str) else str(row[dept_idx])

                if req_name and dept_name:
                    # Find department ID
                    department_id = all_departments.get(dept_name)
                    if not department_id:
                        raise ValidationError(f"Département non trouvé: {dept_name}")

                    # Find requirement with both the exact name and department
                    requirement_key = (req_name, department_id)
                    requirement_id = all_requirements.get(requirement_key)

                    if requirement_id:
                        # Set the requirement_id in the data row
                        row[req_idx] = requirement_id
                    else:
                        # If no requirement found with exact name and department, raise error
                        raise ValidationError(
                            f"Impossible de trouver l'exigence '{req_name}' dans le département '{dept_name}'. "
                            f"Veuillez vérifier que l'exigence existe avec ce nom exact dans ce département.")

        return super(ProjectSubrequirement, self).load(fields, data)
