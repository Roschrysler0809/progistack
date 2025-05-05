from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .common_requirements import COMPLEXITY_SELECTION
from .common_requirements import get_complexity_from_days


class ProjectAbstractSubrequirementLine(models.AbstractModel):
    """
    Abstract model for subrequirement lines.
    Contains common fields and methods used by both standard and custom subrequirement lines.
    """
    _name = 'project.abstract.subrequirement.line'
    _description = "Modèle abstrait pour les lignes de sous-exigence"
    _order = 'order, id'
    _rec_name = 'display_name'

    # Common base fields
    order = fields.Integer(string="Ordre", required=True, default=10,
                           help="Détermine l'ordre d'affichage des sous-exigences")
    complexity = fields.Selection(COMPLEXITY_SELECTION, string="Complexité",
                                  compute='_compute_complexity', store=True, readonly=False)
    estimated_work_days = fields.Float(string="Charge (Jours)", required=True, default=0.0)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('estimated_work_days')
    def _compute_complexity(self):
        """
        Compute complexity level based on estimated days.
        This method ensures complexity is always aligned with the current threshold values.
        """
        for record in self:
            record.complexity = get_complexity_from_days(record.estimated_work_days)

    @api.constrains('estimated_work_days')
    def _check_percentage_values(self):
        for record in self:
            if record.estimated_work_days < 0:
                raise ValidationError(_("La charge en jours ne peut pas être négative"))

    def _compute_display_name(self):
        """To be implemented by inheriting models"""
        for record in self:
            record.display_name = "Ligne de sous-exigence"

    def _get_concrete_model_name(self):
        """
        Return the technical name of the concrete model implementing this abstract model.
        Must be implemented by concrete models.
        """
        raise NotImplementedError()

    def _get_parent_requirement_field_name(self):
        """
        Return the name of the field that points to the parent requirement line.
        Must be implemented by concrete models.
        """
        raise NotImplementedError()

    def _update_parent_requirement_line(self):
        """
        Update the parent requirement line after changes.
        """
        parent_field_name = self._get_parent_requirement_field_name()
        if not parent_field_name:
            return

        for record in self:
            parent = record[parent_field_name]
            if parent:
                parent._compute_estimated_work_days()
                parent._compute_planned_dates()
                parent._compute_estimated_days()
