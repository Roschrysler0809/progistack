from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .common_dates import (
    ensure_business_day,
    get_next_business_day,
    add_working_days,
    adjust_duration_by_workforce
)


class ProjectAbstractRequirementLine(models.AbstractModel):
    """
    Abstract model for requirement lines.
    Contains common fields and methods used by both standard and custom requirement lines.
    """
    _name = 'project.abstract.requirement.line'
    _description = "Modèle abstrait pour les lignes d'exigence"
    _order = 'order, planned_end_date, id'
    _rec_name = 'display_name'

    # Common base fields
    order = fields.Integer(string="Ordre", required=True, default=1,
                           help="Détermine l'ordre d'exécution et les dates planifiées")
    project_id = fields.Many2one('project.project', string="Projet", required=True, ondelete='cascade')

    # Related fields
    project_stage = fields.Selection(related='project_id.stage', string="Étape du projet", readonly=True)
    project_type = fields.Selection(related='project_id.project_type', string="Type de projet", readonly=True)

    # Common content fields
    besoins = fields.Html(string="Besoins", help="Besoins liés à cette exigence")
    challenges = fields.Html(string="Challenges", help="Défis et challenges liés à cette exigence")
    solutions = fields.Html(string="Solutions", help="Solutions proposées pour cette exigence")

    # Display fields
    display_name = fields.Char(string='Nom affiché', compute='_compute_display_name', store=True)
    department_name = fields.Char(string="Department Name", compute="_compute_department_name", store=True)

    # Scheduling and timing fields
    estimated_work_days = fields.Float(string="Charge (Jours)", compute='_compute_estimated_work_days',
                                       store=True, readonly=True,
                                       help="Nombre de jours ouvrés estimés pour cette exigence")
    estimated_days = fields.Float(string="Durée calendaire", compute='_compute_estimated_days',
                                  store=True, readonly=True,
                                  help="Nombre total de jours calendaires estimés (incluant les weekends)")
    planned_start_date = fields.Date(string="Date début planifiée", compute='_compute_planned_dates',
                                     store=True, readonly=True)
    planned_end_date = fields.Date(string="Date fin planifiée", compute='_compute_planned_dates',
                                   store=True, readonly=True)

    # Position indicator fields
    is_first_order = fields.Boolean(string="Est premier ordre", compute="_compute_position_in_order", store=False)
    is_last_order = fields.Boolean(string="Est dernier ordre", compute="_compute_position_in_order", store=False)
    has_parallel_requirements = fields.Boolean(string="A des exigences parallèles",
                                               compute="_compute_position_in_order", store=False)

    # Subrequirement state
    has_modified_subrequirements = fields.Boolean(string="Sous-exigences modifiées",
                                                  compute='_compute_has_modified_subrequirements',
                                                  store=True)

    # Financial fields
    unit_price = fields.Float(string="Prix unitaire", compute='_compute_unit_price', readonly=True,
                              help="Prix journalier moyen basé sur les profils du projet")
    amount = fields.Float(string="Montant", compute='_compute_amount', readonly=True,
                          help="Montant total calculé (Prix unitaire × Charge)")

    # State fields
    can_be_edited = fields.Boolean(string="Peut être modifié", compute='_compute_can_be_edited')

    @api.depends('project_id')
    def _compute_department_name(self):
        """To be implemented by inheriting models"""
        for line in self:
            line.department_name = False

    @api.depends('department_name')
    def _compute_display_name(self):
        """Abstract display name computation - to be overridden by concrete models"""
        for record in self:
            display_parts = []
            if record.department_name:
                display_parts.append(record.department_name)
            record.display_name = display_parts[0] if display_parts else "Ligne d'exigence"

    def name_get(self):
        """Return the display name for each record"""
        return [(record.id, record.display_name) for record in self]

    @api.depends('planned_start_date', 'planned_end_date')
    def _compute_estimated_days(self):
        """
        Calculate total estimated days (calendar days) based on planned start and end dates.
        This reflects the actual calendar duration, including weekends.
        """
        for record in self:
            if record.planned_start_date and record.planned_end_date:
                # Calculate total calendar days (including both start and end date)
                days_diff = (record.planned_end_date - record.planned_start_date).days + 1
                record.estimated_days = max(0, days_diff)
            else:
                record.estimated_days = 0

    def _compute_estimated_work_days(self):
        """To be implemented by inheriting models"""
        for record in self:
            record.estimated_work_days = 0

    @api.depends('project_stage', 'project_type')
    def _compute_can_be_edited(self):
        """Compute whether this requirement line can be edited based on project state"""
        for record in self:
            # If in project stage, only etude_chiffrage projects can be edited
            if record.project_stage == 'project' and record.project_type != 'etude_chiffrage':
                record.can_be_edited = False
            else:
                record.can_be_edited = True

    @api.depends('unit_price', 'estimated_work_days')
    def _compute_amount(self):
        """Compute total amount based on unit price and estimated work days"""
        for record in self:
            record.amount = record.unit_price * record.estimated_work_days

    @api.depends('project_id', 'project_id.profile_line_ids', 'project_id.profile_line_ids.daily_rate',
                 'project_id.profile_line_ids.involvement_percentage')
    def _compute_unit_price(self):
        """Compute unit price based on the project's average daily rate"""
        for record in self:
            unit_price = 0
            if record.project_id and record.project_id.profile_line_ids:
                total_weighted_rate = 0
                total_profiles = len(record.project_id.profile_line_ids)

                if total_profiles > 0:
                    for profile in record.project_id.profile_line_ids:
                        total_weighted_rate += profile.daily_rate * profile.involvement_percentage

                    unit_price = total_weighted_rate / total_profiles

            record.unit_price = unit_price

    @api.constrains('order')
    def _check_order(self):
        """Ensure order is not negative"""
        for record in self:
            if record.order < 0:
                raise ValidationError("L'ordre ne peut pas être négatif.")

    @api.constrains('estimated_days')
    def _check_estimated_days(self):
        """Validate that estimated days are not negative"""
        for record in self:
            if record.estimated_days < 0:
                raise ValidationError("La durée calendaire ne peut pas être négative.")

    @api.constrains('planned_start_date', 'planned_end_date')
    def _check_planned_dates(self):
        """Ensure planned end date is not before start date"""
        for record in self:
            if record.planned_start_date and record.planned_end_date and record.planned_end_date < record.planned_start_date:
                raise ValidationError("La date de fin planifiée ne peut pas être antérieure à la date de début.")

    @api.constrains('project_id')
    def _check_project_id(self):
        """Ensure project_id is set"""
        for record in self:
            if not record.project_id:
                raise ValidationError("Une ligne d'exigence doit être associée à un projet.")

    def _get_requirement_lines_for_project(self):
        """
        Abstract method to get requirement lines for the project.
        Must be implemented by concrete models.
        """
        raise NotImplementedError()

    def _get_concrete_model_name(self):
        """
        Return the technical name of the concrete model implementing this abstract model.
        Must be implemented by concrete models.
        """
        raise NotImplementedError()

    @api.depends('order', 'project_id')
    def _compute_position_in_order(self):
        """Determine if requirement is first/last in sequence and if it has parallel requirements"""
        for record in self:
            if not record.project_id or not record.order:
                record.is_first_order = False
                record.is_last_order = False
                record.has_parallel_requirements = False
                continue

            requirement_lines = record._get_requirement_lines_for_project()
            all_orders = sorted(set(requirement_lines.mapped('order')))

            record.is_first_order = all_orders and record.order == all_orders[0]
            record.is_last_order = all_orders and record.order == all_orders[-1]

            parallel_reqs = requirement_lines.filtered(
                lambda r: r.id != record.id and r.order == record.order
            )
            record.has_parallel_requirements = bool(parallel_reqs)

    def action_clear_subrequirement_lines(self):
        """
        Abstract method to clear subrequirement lines.
        Must be implemented by concrete models.
        """
        raise NotImplementedError()

    def _compute_has_modified_subrequirements(self):
        """Abstract method to compute modified state - must be implemented by concrete models"""
        raise NotImplementedError()

    def _compute_planned_dates(self):
        """Compute planned start and end dates for requirement lines."""
        for line in self:
            if not line.project_id or not line.project_id.date_start:
                line.planned_start_date = False
                line.planned_end_date = False
                continue

            project = line.project_id
            project_start_date = project.date_start

            # Calculate workforce factor
            workforce_factor = 1.0
            if project.profile_line_ids:
                total_involvement = sum(profile.involvement_percentage for profile in project.profile_line_ids if
                                        profile.involvement_percentage)
                if total_involvement > 0:
                    workforce_factor = total_involvement

            # Group all requirement lines by order
            lines_by_order = {}
            for req_line in self._get_requirement_lines_for_project():
                order = req_line.order or 0
                if order not in lines_by_order:
                    lines_by_order[order] = []
                lines_by_order[order].append(req_line)

            # Sort orders for processing in sequence
            sorted_orders = sorted(lines_by_order.keys())

            # Start with project start date (ensure it's a business day)
            current_date = ensure_business_day(project_start_date)

            # Process each order until we reach the current line's order
            for order in sorted_orders:
                if order < line.order:
                    # For previous orders, find their earliest end date (minimum)
                    end_dates = []
                    for req_line in lines_by_order[order]:
                        working_days = req_line.estimated_work_days or 0
                        duration_days = adjust_duration_by_workforce(working_days, workforce_factor)
                        end_date = add_working_days(current_date, duration_days)
                        end_dates.append(end_date)

                    if end_dates:
                        # Next order starts after the earliest end date in current order
                        current_date = get_next_business_day(min(end_dates))

                elif order == line.order:
                    # This is our line's order, calculate its dates
                    line.planned_start_date = current_date

                    # Calculate end date based on working days and workforce factor
                    working_days = line.estimated_work_days or 0
                    duration_days = adjust_duration_by_workforce(working_days, workforce_factor)
                    end_date = add_working_days(current_date, duration_days)
                    line.planned_end_date = end_date
                    break

    def _reorder_project_requirements(self, project_id=None):
        """
        Abstract template method for reordering requirements.
        This implements the common algorithm but delegates the actual requirement line fetching to concrete models.
        """
        if not project_id and not self:
            return

        # Get project and requirements
        project = project_id and self.env['project.project'].browse(project_id) or self[0].project_id
        if not project:
            return

        # Concrete models must provide proper implementation of _get_concrete_model_name
        model_name = self._get_concrete_model_name()
        all_req_lines = self.env[model_name].search([
            ('project_id', '=', project.id)
        ], order='order, id')

        if not all_req_lines:
            return

        # Group by order to preserve parallel requirements
        order_mapping = {}
        for line in all_req_lines:
            if line.order not in order_mapping:
                order_mapping[line.order] = []
            order_mapping[line.order].append(line)

        # Create new sequential ordering
        sorted_orders = sorted(order_mapping.keys())
        new_order_mapping = {}
        new_order = 1

        for old_order in sorted_orders:
            if old_order > new_order:  # Gap found
                new_order_mapping[old_order] = new_order
                new_order += 1
            elif old_order < new_order:  # Duplicate or out-of-sequence
                new_order_mapping[old_order] = new_order
                new_order += 1
            else:  # Order already matches expected value
                new_order_mapping[old_order] = old_order
                new_order += 1

        # Apply new orders while preserving parallel groups
        for old_order, lines in order_mapping.items():
            new_order = new_order_mapping[old_order]
            if old_order != new_order:
                for line in lines:
                    line.with_context(skip_reordering=True).sudo().write({'order': new_order})

        # Refresh computed fields
        if all_req_lines:
            all_req_lines.invalidate_recordset(['planned_start_date', 'planned_end_date'])

    def action_move_up(self):
        """Move requirement one position up by swapping with previous order"""
        self.ensure_one()

        if not self.project_id:
            return

        requirement_lines = self._get_requirement_lines_for_project()
        all_orders = sorted(set(requirement_lines.mapped('order')))

        # Find previous order
        current_index = all_orders.index(self.order) if self.order in all_orders else -1
        if current_index <= 0:  # Already at top
            return

        previous_order = all_orders[current_index - 1]
        previous_reqs = requirement_lines.filtered(
            lambda r: r.order == previous_order
        )

        if not previous_reqs:
            return

        # Swap orders
        self.with_context(skip_reordering=True).write({'order': previous_order})
        previous_reqs.with_context(skip_reordering=True).write({'order': self.order})

        self._reorder_project_requirements()
        return True

    def action_move_down(self):
        """
        Move requirement one position down.
        For last parallel requirement: create new order
        Otherwise: swap with next order
        """
        self.ensure_one()

        if not self.project_id:
            return

        requirement_lines = self._get_requirement_lines_for_project()
        all_orders = sorted(set(requirement_lines.mapped('order')))

        # Special case: last order with parallel requirements
        if self.order == all_orders[-1] and self.has_parallel_requirements:
            self.with_context(skip_reordering=True).write({'order': self.order + 1})
            self._reorder_project_requirements()
            return True

        # Standard case: swap with next order
        current_index = all_orders.index(self.order) if self.order in all_orders else -1
        if current_index < 0 or current_index >= len(all_orders) - 1:  # At bottom
            return

        next_order = all_orders[current_index + 1]
        next_reqs = requirement_lines.filtered(
            lambda r: r.order == next_order
        )

        if not next_reqs:
            return

        # Swap orders
        self.with_context(skip_reordering=True).write({'order': next_order})
        next_reqs.with_context(skip_reordering=True).write({'order': self.order})

        self._reorder_project_requirements()
        return True

    def action_make_next_order(self):
        """Move this requirement to the next available order"""
        self.ensure_one()

        if not self.project_id:
            return

        # Find next available order
        requirement_lines = self._get_requirement_lines_for_project()
        max_order = max(requirement_lines.mapped('order') or [0])
        self.write({'order': max_order + 1})
        self._reorder_project_requirements()

        return {'type': 'ir.actions.act_window_close'}

    def action_open_form(self):
        """Opens the requirement line form view."""
        self.ensure_one()

        # Check if the project is in project stage and not an etude_chiffrage project
        if (self.project_stage == 'project' and self.project_type != 'etude_chiffrage'):
            raise UserError(_("Impossible de modifier une ligne d'exigence en phase projet."))

        # Get model name from current record
        model_name = self._name

        return {
            'name': _('Modifier la ligne d\'exigence'),
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create method to ensure proper ordering and validation.
        """
        # Process each set of values in the batch
        for vals in vals_list:
            # Validate project_id is provided
            if not vals.get('project_id'):
                raise ValidationError("Une ligne d'exigence doit être associée à un projet.")

            # If no order is specified, find the next available order number
            if 'order' not in vals and 'project_id' in vals:
                requirement_lines = self.env[self._get_concrete_model_name()].search([
                    ('project_id', '=', vals['project_id'])
                ])
                existing_orders = requirement_lines.mapped('order')
                vals['order'] = max(existing_orders + [0]) + 1

        # Call super to create the records
        result = super(ProjectAbstractRequirementLine, self).create(vals_list)

        # Trigger reordering after creating new requirement lines (unless skip_reordering is set)
        if result and not self.env.context.get('skip_reordering'):
            # Group by project to avoid multiple reorderings of the same project
            projects_to_reorder = set(req_line.project_id.id for req_line in result)
            for project_id in projects_to_reorder:
                self._reorder_project_requirements(project_id)

        return result

    def write(self, vals):
        """Override write method to handle reordering properly."""
        # Track changed orders for later reordering
        order_changed = 'order' in vals
        projects_to_reorder = set()

        if order_changed:
            # Store project IDs before write
            projects_to_reorder = set(line.project_id.id for line in self)

            # Store original orders to detect if they've actually changed
            # This helps prevent unnecessary reordering
            self_orders = {rec.id: rec.order for rec in self}

        # Call super to update the records
        result = super(ProjectAbstractRequirementLine, self).write(vals)

        # Trigger reordering if order changed and not skipped
        # Only reorder if we're not in the middle of a project save operation
        if (order_changed and
                not self.env.context.get('skip_reordering') and
                not self.env.context.get('__import_validate')):  # This is set during form save validation

            # Verify the order actually changed for at least one record
            order_actually_changed = False
            for record in self:
                if record.id in self_orders and self_orders[record.id] != record.order:
                    order_actually_changed = True
                    break

            if order_actually_changed:
                for project_id in projects_to_reorder:
                    self._reorder_project_requirements(project_id)

        return result

    def unlink(self):
        """Override unlink to trigger recalculation of dates for remaining lines after deletion"""
        # Save project references before deletion
        projects = self.mapped('project_id')

        # Delete the records
        result = super(ProjectAbstractRequirementLine, self).unlink()

        # Trigger reordering after deletion
        if projects and not self.env.context.get('skip_reordering'):
            for project in projects:
                self._reorder_project_requirements(project.id)

        # Invalidate the cache for remaining lines to ensure proper recomputation
        if projects:
            model_name = self._get_concrete_model_name()
            remaining_lines = self.env[model_name].search([('project_id', 'in', projects.ids)])
            if remaining_lines:
                remaining_lines.invalidate_recordset(['planned_start_date', 'planned_end_date'])

        return result
