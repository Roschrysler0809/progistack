from odoo import models, fields, _, api
from odoo.exceptions import UserError
from .common import PROJECT_STATUS_SELECTION


class ProjectFlashReportLine(models.Model):
    _name = 'project.flash.report.line'
    _description = 'Ligne de Flash Report du Projet'
    _order = 'lot_number, department'

    project_update_id = fields.Many2one('project.update', string='Mise à jour du projet',
                                        required=True, ondelete='cascade', readonly=True)
    project_id = fields.Many2one(related='project_update_id.project_id', string='Projet',
                                 store=True, readonly=True)
    department = fields.Char(string='Département', required=True)
    project_status = fields.Selection(PROJECT_STATUS_SELECTION, string='Statut du projet', required=True,
                                      default='sunny')
    tasks_completed = fields.Html(string='Tâches réalisées')
    tasks_in_progress = fields.Html(string='Tâches en cours')
    upcoming_deliveries = fields.Html(string='Prochaines étapes')
    attention_points = fields.Html(string='Points d\'attention')
    is_report_sent = fields.Boolean(string="Rapport envoyé", compute="_compute_is_report_sent", store=True)

    # Get the report date from the parent update
    report_date = fields.Datetime(related='project_update_id.report_date',
                                  string='Date du rapport', readonly=True, store=True)

    # For backward compatibility
    date = fields.Date(related='project_update_id.date',
                       string='Date du rapport', readonly=True, store=True)

    # Lot number for ordering in flash report
    lot_number = fields.Integer(string='Numéro de lot', readonly=True)

    @api.depends('project_update_id.state')
    def _compute_is_report_sent(self):
        for line in self:
            line.is_report_sent = line.project_update_id.state == 'sent'

    def open_form(self):
        """Opens the flash report line form view."""
        self.ensure_one()

        # Check if the report is in sent state
        if self.project_update_id.state == 'sent':
            raise UserError(_("Impossible de modifier une ligne de rapport envoyé. Le rapport a été verrouillé."))

        return {
            'name': 'Modifier la ligne de Flash Report',
            'type': 'ir.actions.act_window',
            'res_model': 'project.flash.report.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
