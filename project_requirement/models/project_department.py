from odoo import models, fields
from odoo.exceptions import UserError


class ProjectDepartment(models.Model):
    _name = 'project.department'
    _description = 'Département de projet'
    _rec_name = 'name'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string="Nom", required=True)
    short_name = fields.Char(string="Nom court", help="Version courte du nom du département (ex: RH)")
    code = fields.Char(string="Code", required=True,
                       help="Identifiant unique du département")
    color = fields.Integer(string="Couleur")
    is_readonly = fields.Boolean(string="En lecture seule", default=False,
                                 help="Si activé, ce département ne peut pas être modifié ou supprimé")

    _sql_constraints = [
        ('unique_department_code', 'UNIQUE(code)', 'Le code du département doit être unique!')
    ]

    def unlink(self):
        """Prevent deletion of readonly departments (like the generic department)"""
        for department in self:
            if department.is_readonly:
                raise UserError(
                    f"Le département '{department.name}' ne peut pas être supprimé car il est en lecture seule.")
        return super(ProjectDepartment, self).unlink()
