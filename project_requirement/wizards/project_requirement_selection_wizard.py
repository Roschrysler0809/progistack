import json  # Add json import for domain serialization

from odoo import api, fields, models


class ProjectRequirementSelectionWizard(models.TransientModel):
    _name = 'project.requirement.selection.wizard'
    _description = 'Assistant de sélection des exigences'

    project_id = fields.Many2one('project.project', string='Projet', required=True, readonly=True)
    requirement_ids = fields.Many2many('project.requirement', string='Exigences disponibles')
    available_requirement_domain = fields.Char(string="Domain for requirements", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super(ProjectRequirementSelectionWizard, self).default_get(fields_list)

        project_id = self.env.context.get('active_id')
        if project_id:
            project = self.env['project.project'].browse(project_id)
            res['project_id'] = project_id

            # Get selected departments in the project
            department_ids = project.department_ids.ids

            # Retrieve all requirements related to the project's departments
            # NOTE: Requirements themselves do not have a direct project_type field
            domain = [
                ('department_id', 'in', department_ids)
            ]
            all_dept_requirements = self.env['project.requirement'].search(domain)

            # Retrieve requirements already present in the project
            existing_req_ids = project.requirement_line_ids.mapped('requirement_id.id')

            # Filter only missing requirements IDs
            missing_requirement_ids = all_dept_requirements.filtered(lambda r: r.id not in existing_req_ids).ids

            # Set the domain for the Many2many field
            # We store it as a JSON string because domains aren't directly storable
            res['available_requirement_domain'] = json.dumps([
                ('id', 'in', missing_requirement_ids)
            ])

            # Do NOT pre-populate requirement_ids, the user will select them
            # res['requirement_ids'] = [(6, 0, [])] # Not needed

        return res

    def action_confirm(self):
        """Ajouter les exigences sélectionnées au projet"""
        self.ensure_one()

        # The selected requirements are now directly in self.requirement_ids
        if not self.requirement_ids:
            return {'type': 'ir.actions.act_window_close'}

        # Add each selected requirement to the project
        for requirement in self.requirement_ids:
            self.env['project.requirement.line'].create({
                'project_id': self.project_id.id,
                'requirement_id': requirement.id,
                # Copy default values if needed, like estimated days
                # 'estimated_work_days': requirement.estimated_work_days,
                # 'estimated_days': requirement.estimated_days,
            })

        # Reorder the requirements if necessary (optional)
        self.project_id._reorder_requirements_after_save()

        return {'type': 'ir.actions.act_window_close'}
