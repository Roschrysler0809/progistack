from odoo import api
from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError


class ProjectTrackingReportLine(models.Model):
    _name = 'project.tracking.report.line'
    _description = 'Ligne de Suivi Projet'
    _order = 'department, id'

    project_update_id = fields.Many2one('project.update', string='Mise à jour du projet',
                                        required=True, ondelete='cascade', readonly=True)
    project_id = fields.Many2one(related='project_update_id.project_id', string='Projet',
                                 store=True, readonly=True)
    requirement = fields.Char(string='Exigence', readonly=True)
    subrequirement = fields.Char(string='Sous-exigence', readonly=True)
    department = fields.Char(string='Département', readonly=True)
    lot_number = fields.Char(string='Lot', readonly=True)
    design_implementation_percentage = fields.Float(string='% Conception & Implémentation')
    validation_percentage = fields.Float(string='% Validation')
    integration_percentage = fields.Float(string='% Integration')
    mep_planned_date = fields.Date(string="Date MEP prévue", readonly=True)
    mep_actual_date = fields.Date(string="Date MEP réelle")
    delivery_planned_date = fields.Date(string="Date Livraison prévue", readonly=True)
    delivery_actual_date = fields.Date(string="Date Livraison réelle")
    comments = fields.Text(string='Commentaires')
    is_report_sent = fields.Boolean(string="Rapport envoyé", compute="_compute_is_report_sent", store=True)

    # Additional fields for referencing the actual requirement/subrequirement
    requirement_line_id = fields.Many2one('project.requirement.line', string='Ligne d\'exigence', readonly=True)
    subrequirement_line_id = fields.Many2one('project.subrequirement.line', string='Ligne de sous-exigence',
                                             readonly=True)

    # Get the report date from the parent update
    report_date = fields.Datetime(related='project_update_id.report_date',
                                  string='Date du rapport', readonly=True, store=True)

    # For backward compatibility
    date = fields.Date(related='project_update_id.date',
                       string='Date du rapport', readonly=True, store=True)

    @api.constrains('design_implementation_percentage', 'validation_percentage', 'integration_percentage')
    def _check_percentage_values(self):
        for record in self:
            for field in ['design_implementation_percentage', 'validation_percentage', 'integration_percentage']:
                value = record[field]
                if value < 0 or value > 100:
                    field_name = record._fields[field].string
                    raise ValidationError(_("Le pourcentage '%s' doit être compris entre 0 et 100") % field_name)

    @api.depends('project_update_id.state')
    def _compute_is_report_sent(self):
        for line in self:
            line.is_report_sent = line.project_update_id.state == 'sent'

    def open_form(self):
        """Opens the tracking report line form view."""
        self.ensure_one()

        # Check if the report is in sent state
        if self.project_update_id.state == 'sent':
            raise UserError(_("Impossible de modifier une ligne de rapport envoyé. Le rapport a été verrouillé."))

        return {
            'name': 'Modifier la ligne de Suivi Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.tracking.report.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
