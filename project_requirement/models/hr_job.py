from odoo import models, fields, api


class HrJob(models.Model):
    """
    Extend the HR Job model to include project role fields
    """
    _inherit = 'hr.job'

    # Project role fields
    currency_id = fields.Many2one('res.currency', string="Devise",
                                  compute='_compute_currency_id', store=True,
                                  help="Devise utilisée pour le taux journalier")
    default_daily_rate = fields.Monetary(string="Taux journalier par défaut",
                                         currency_field='currency_id',
                                         help="Taux journalier suggéré pour ce rôle")

    @api.depends('create_date')
    def _compute_currency_id(self):
        """Compute currency based on company currency"""
        company_currency = self.env.company.currency_id
        for record in self:
            record.currency_id = company_currency
