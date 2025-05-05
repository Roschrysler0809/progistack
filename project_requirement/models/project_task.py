from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .common_requirements import START_WORK_TIME, END_WORK_TIME, HOURS_PER_DAY


class ProjectTask(models.Model):
    _inherit = 'project.task'

    requirement_id = fields.Many2one('project.requirement', string='Exigence', readonly=True,
                                     help="Exigence associée à cette tâche",
                                     ondelete='set null', index=True)
    # Allow allocated_hours to be editable but computed when requirement exists
    allocated_hours = fields.Float(compute='_compute_requirement_allocated_hours', store=True)

    # References to requirement lines
    requirement_line_id = fields.Many2one('project.requirement.line', string="Ligne d'exigence",
                                          readonly=True, copy=False)
    custom_requirement_line_id = fields.Many2one('project.custom.requirement.line',
                                                 string="Ligne d'exigence personnalisée",
                                                 readonly=True, copy=False)

    # Computed fields for display purposes
    requirement_name = fields.Char(string="Nom de l'exigence", compute="_compute_requirement_info", store=True)
    department_name = fields.Char(string="Nom du département", compute="_compute_requirement_info", store=True)

    @api.depends('requirement_id', 'project_id', 'requirement_line_id', 'custom_requirement_line_id')
    def _compute_requirement_allocated_hours(self):
        """
        Set allocated hours based on the requirement's estimated work days.
        This handles both standard requirement lines and custom requirement lines.
        
        For standard requirements:
            - Find the requirement line in the project that matches this task's requirement
        
        For custom requirements:
            - Use the custom requirement line directly
        
        Convert days to hours using HOURS_PER_DAY constant
        """
        for task in self:
            # Skip computation for tasks without any requirement reference - keep existing value for manual entry
            if not (task.requirement_id or task.requirement_line_id or task.custom_requirement_line_id):
                continue

            allocated_hours = 0

            # Check for custom requirement line first (used in evolution projects)
            if task.custom_requirement_line_id and task.custom_requirement_line_id.estimated_work_days:
                estimated_days = task.custom_requirement_line_id.estimated_work_days or 1
                allocated_hours = estimated_days * HOURS_PER_DAY

            # Check for standard requirement line if no custom requirement line is set
            elif task.requirement_line_id and task.requirement_line_id.estimated_work_days:
                estimated_days = task.requirement_line_id.estimated_work_days or 1
                allocated_hours = estimated_days * HOURS_PER_DAY

            # Fallback to requirement lookup if neither direct line reference exists but requirement_id is set
            elif task.project_id and task.requirement_id:
                # Find the requirement line in the project that matches this task's requirement
                requirement_line = self.env['project.requirement.line'].search([
                    ('project_id', '=', task.project_id.id),
                    ('requirement_id', '=', task.requirement_id.id)
                ], limit=1)

                # If found, use its estimated_work_days
                if requirement_line and requirement_line.estimated_work_days:
                    estimated_days = requirement_line.estimated_work_days or 1
                    allocated_hours = estimated_days * HOURS_PER_DAY

            task.allocated_hours = allocated_hours

    @api.depends('requirement_line_id', 'custom_requirement_line_id')
    def _compute_requirement_info(self):
        """
        Compute requirement name and department for display purposes.
        This handles both standard and custom requirement lines.
        """
        for task in self:
            if task.requirement_line_id:
                # Standard requirement line
                requirement = task.requirement_line_id.requirement_id
                task.requirement_name = requirement.name if requirement else False
                task.department_name = requirement.department_id.name if requirement and requirement.department_id else False
            elif task.custom_requirement_line_id:
                # Custom requirement line (for evolution projects)
                task.requirement_name = task.custom_requirement_line_id.name
                task.department_name = task.custom_requirement_line_id.department_id.name if task.custom_requirement_line_id.department_id else False
            else:
                # No requirement reference
                task.requirement_name = False
                task.department_name = False

    @api.onchange('planned_date_begin')
    def _onchange_planned_date_begin(self):
        """Set start time to START_WORK_TIME when a new date is set or time is midnight"""
        if not self.planned_date_begin:
            return

        # Always set standard start time for newly added dates or midnight times
        if self._origin.planned_date_begin is False or self.planned_date_begin.time() == datetime.min.time():
            self.planned_date_begin = datetime.combine(
                self.planned_date_begin.date(),
                START_WORK_TIME
            )

    @api.onchange('date_deadline')
    def _onchange_date_deadline(self):
        """Set end time to END_WORK_TIME when a new date is set or time is midnight/end of day"""
        if not self.date_deadline:
            return

        current_time = self.date_deadline.time()
        # Always set standard end time for newly added dates or default times
        if self._origin.date_deadline is False or current_time == datetime.min.time() or current_time == datetime.max.time():
            self.date_deadline = datetime.combine(
                self.date_deadline.date(),
                END_WORK_TIME
            )

    @api.constrains('planned_date_begin', 'date_deadline')
    def _check_task_date_consistency(self):
        """Ensure task end date is not earlier than its start date"""
        # Skip check if no tasks need validation
        if not self:
            return

        # Process in batches for better performance
        for task in self:
            # Skip if missing either date
            if not task.planned_date_begin or not task.date_deadline:
                continue

            # Check date consistency
            if task.date_deadline < task.planned_date_begin:
                start_date = task.planned_date_begin.strftime('%d/%m/%Y %H:%M')
                end_date = task.date_deadline.strftime('%d/%m/%Y %H:%M')
                raise ValidationError(_("La date d'échéance de la tâche '%(task_name)s' (%(end_date)s) "
                                        "doit être > à sa date de début (%(start_date)s).") %
                                      {
                                          'task_name': task.name,
                                          'end_date': end_date,
                                          'start_date': start_date,
                                      })

    @api.constrains('planned_date_begin', 'parent_id')
    def _check_subtask_start_date_constraints(self):
        """Ensure subtask start date is within parent task timeframe"""
        # Skip check if no tasks need validation
        if not self:
            return

        # Process only tasks with parents and start dates (direct access is faster than filtered)
        parent_dict = {}
        for task in self:
            # Skip if missing required fields
            if not task.parent_id or not task.planned_date_begin:
                continue

            # Cache parent to avoid multiple lookups
            parent_id = task.parent_id.id
            if parent_id not in parent_dict:
                parent_dict[parent_id] = task.parent_id

            parent = parent_dict[parent_id]
            if not parent.planned_date_begin:
                continue

            # 1. Check if subtask start date is before parent start date
            if task.planned_date_begin < parent.planned_date_begin:
                parent_date = parent.planned_date_begin.strftime('%d/%m/%Y %H:%M')
                subtask_date = task.planned_date_begin.strftime('%d/%m/%Y %H:%M')
                raise ValidationError(_("La date de début de la sous-tâche '%(subtask_name)s' (%(subtask_date)s) "
                                        "doit être > à celle de la tâche (%(parent_date)s).") %
                                      {
                                          'subtask_name': task.name,
                                          'subtask_date': subtask_date,
                                          'parent_date': parent_date,
                                      })

            # 2. Check if subtask start date is after parent end date
            if parent.date_deadline and task.planned_date_begin > parent.date_deadline:
                parent_date = parent.date_deadline.strftime('%d/%m/%Y %H:%M')
                subtask_date = task.planned_date_begin.strftime('%d/%m/%Y %H:%M')
                raise ValidationError(_("La date de début de la sous-tâche '%(subtask_name)s' (%(subtask_date)s) "
                                        "doit être < à la date de fin de la tâche (%(parent_date)s).") %
                                      {
                                          'subtask_name': task.name,
                                          'subtask_date': subtask_date,
                                          'parent_date': parent_date,
                                      })

    @api.constrains('date_deadline', 'parent_id')
    def _check_subtask_end_date_constraints(self):
        """Ensure subtask end date is within parent task timeframe"""
        # Skip check if no tasks need validation
        if not self:
            return

        # Process only tasks with parents and end dates (direct access is faster than filtered)
        parent_dict = {}
        for task in self:
            # Skip if missing required fields
            if not task.parent_id or not task.date_deadline:
                continue

            # Cache parent to avoid multiple lookups
            parent_id = task.parent_id.id
            if parent_id not in parent_dict:
                parent_dict[parent_id] = task.parent_id

            parent = parent_dict[parent_id]
            if not parent.planned_date_begin:
                continue

            # 1. Check if subtask end date is after parent end date
            if parent.date_deadline and task.date_deadline > parent.date_deadline:
                parent_date = parent.date_deadline.strftime('%d/%m/%Y %H:%M')
                subtask_date = task.date_deadline.strftime('%d/%m/%Y %H:%M')
                raise ValidationError(_("La date de fin de la sous-tâche '%(subtask_name)s' (%(subtask_date)s) "
                                        "doit être < à celle de la tâche (%(parent_date)s).") %
                                      {
                                          'subtask_name': task.name,
                                          'subtask_date': subtask_date,
                                          'parent_date': parent_date,
                                      })

            # 2. Check if subtask end date is before parent start date
            if task.date_deadline < parent.planned_date_begin:
                parent_date = parent.planned_date_begin.strftime('%d/%m/%Y %H:%M')
                subtask_date = task.date_deadline.strftime('%d/%m/%Y %H:%M')
                raise ValidationError(_("La date de fin de la sous-tâche '%(subtask_name)s' (%(subtask_date)s) "
                                        "doit être > à la date de début de la tâche (%(parent_date)s).") %
                                      {
                                          'subtask_name': task.name,
                                          'subtask_date': subtask_date,
                                          'parent_date': parent_date,
                                      })

    @api.constrains('allocated_hours', 'parent_id')
    def _check_subtask_allocated_hours_constraint(self):
        """Ensure total allocated hours of subtasks is less than parent task's allocated hours"""
        # Skip check if no tasks need validation
        if not self:
            return

        # Process only tasks with parents and allocated hours
        parent_dict = {}
        for task in self:
            # Skip if missing required fields
            if not task.parent_id or not task.allocated_hours:
                continue

            # Cache parent to avoid multiple lookups
            parent_id = task.parent_id.id
            if parent_id not in parent_dict:
                parent_dict[parent_id] = task.parent_id

            parent = parent_dict[parent_id]
            if not parent.allocated_hours:
                continue

            # Calculate total allocated hours of all subtasks
            subtask_total_hours = sum(subtask.allocated_hours for subtask in parent.child_ids)

            # Check if subtask total hours exceeds parent allocated hours
            if subtask_total_hours > parent.allocated_hours:
                raise ValidationError(_("Le temps total alloué des sous-tâches (%(subtask_hours)s heures) "
                                        "doit être inférieur au temps alloué de la tâche parent (%(parent_hours)s heures).") % {
                                          'subtask_hours': subtask_total_hours,
                                          'parent_hours': parent.allocated_hours,
                                      })

    def action_view_requirement_line(self):
        """Open the requirement form view"""
        self.ensure_one()
        if not self.requirement_id:
            return False
        return {
            'name': "Exigence",
            'type': 'ir.actions.act_window',
            'res_model': 'project.requirement',
            'view_mode': 'form',
            'res_id': self.requirement_id.id,
            'target': 'current',
        }

    @api.model
    def _get_default_stage_id(self):
        """Override default stage method to use 'A Faire' stage as default when available."""
        # Try to get the 'Todo' stage first
        todo_stage = self.env.ref('project_requirement.project_task_type_todo', raise_if_not_found=False)
        if todo_stage and self._check_stage_in_project(todo_stage):
            return todo_stage.id

        # Otherwise fall back to standard Odoo behavior for backwards compatibility
        return super()._get_default_stage_id()

    def _check_stage_in_project(self, stage):
        """Check if the stage is available in the project."""
        if not self.env.context.get('default_project_id'):
            return True

        project = self.env['project.project'].browse(self.env.context['default_project_id'])
        if not project.exists():
            return True

        # If project has no specific stages or this stage is in the project's stages
        if not project.type_ids:
            return True

        # Check if stage is in project's stages
        stage_in_project = stage.id in project.type_ids.ids

        # If stage is not in project, add it automatically
        if not stage_in_project:
            project.write({'type_ids': [(4, stage.id)]})
            return True

        return stage_in_project
