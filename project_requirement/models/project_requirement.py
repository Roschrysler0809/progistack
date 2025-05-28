from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectRequirement(models.Model):
    _name = 'project.requirement'
    _description = 'Exigence'
    _rec_name = 'name'
    _order = 'sequence, id'
    _sql_constraints = [
        ('unique_name_department', 'unique(name, department_id)',
         'Une exigence avec ce nom existe déjà pour ce département!')
    ]

    TYPE_SELECTION = [
        ('internal', 'Exigence Interne'),
        ('external', 'Exigence Externe')
    ]

    sequence = fields.Integer(string='Sequence', default=1)
    name = fields.Char(string="Nom", required=True)
    type = fields.Selection(TYPE_SELECTION, string="Type", required=True, default='external')
    department_id = fields.Many2one('project.department', string="Département", required=True )
    estimated_work_days = fields.Float(string="Total Charge (Jours)", compute='_compute_estimated_work_days',
                                       readonly=True, store=True)
    subrequirement_ids = fields.One2many('project.subrequirement', 'requirement_id',
                                         string="Sous-exigences")
    department_can_change = fields.Boolean(compute='_compute_department_can_change',
                                           string="Département modifiable", default=True, store=True)

    def name_get(self):
        result = []
        for record in self:
            type_display = dict(self._fields['type'].selection).get(record.type)
            name = f"{record.name} ({type_display})"
            result.append((record.id, name))
        return result

    @api.depends('subrequirement_ids', 'subrequirement_ids.estimated_work_days')
    def _compute_estimated_work_days(self):
        """Sum up work days from all subrequirements"""
        for record in self:
            # Store the current value to avoid unnecessary updates
            current_value = record.estimated_work_days
            new_value = sum(record.subrequirement_ids.mapped('estimated_work_days'))
            if current_value != new_value:
                record.estimated_work_days = new_value

    @api.depends('department_id', 'subrequirement_ids', 'subrequirement_ids.department_id')
    def _compute_department_can_change(self):
        """
        Determines if the department can be changed. Department cannot be changed
        if there is at least one subrequirement for this requirement.
        """
        for record in self:
            # Default value - allow change
            can_change = True

            # If there's a valid record with subrequirements
            if record.id and record.subrequirement_ids:
                # If there are any subrequirements, department cannot be changed
                can_change = False

            record.department_can_change = can_change

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to ensure estimated_work_days is up-to-date when viewing list"""
        records = super().search(domain or [], offset=offset, limit=limit, order=order)
        records._compute_estimated_work_days()
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    def read(self, fields=None, load='_classic_read'):
        """Override read to ensure estimated_work_days is up-to-date when viewing a record"""
        self._compute_estimated_work_days()
        return super().read(fields=fields, load=load)

    @api.constrains('department_id')
    def _check_department_change_with_subrequirements(self):
        """Prevent changing a requirement's department if it has subrequirements"""
        for record in self:
            # Skip if this is a new record or if department_id hasn't changed
            if not record._origin.id or record.department_id == record._origin.department_id:
                continue

            # Check if the requirement has subrequirements
            subrequirements = self.env['project.subrequirement'].search_count([
                ('requirement_id', '=', record.id)
            ])

            if subrequirements > 0:
                # Raise a validation error to prevent the change
                raise ValidationError(
                    _("Impossible de changer le département d'une exigence qui a des sous-exigences. "
                      "Veuillez supprimer toutes les sous-exigences avant de changer le département.")
                )

    def write(self, vals):
        """Override write to handle department changes with confirmation"""
        return super(ProjectRequirement, self).write(vals)
