from odoo import models, fields, api


class ProjectProfileLine(models.Model):
    """
    This model represents a profile line in a project.
    Each profile line defines a role with a daily rate and involvement percentage.
    """
    _name = 'project.profile.line'
    _description = "Ligne de profil"
    _order = 'id'
    _rec_name = 'role_id'

    INVOLVEMENT_TYPES = [
        ('quarter', '1/4 de Temps'),
        ('half', 'Temps partiel'),
        ('three_quarter', '3/4 de Temps'),
        ('full', 'Temps plein')
    ]

    project_id = fields.Many2one('project.project', string="Projet",
                                 required=True, ondelete='cascade')
    project_stage = fields.Selection(related='project_id.stage', string="Étape du projet", store=True)
    role_id = fields.Many2one('hr.job', string="Rôle", required=True,
                              help="Rôle ou profil pour ce projet")
    currency_id = fields.Many2one('res.currency', string="Devise", compute='_compute_currency_id', store=True)
    daily_rate = fields.Monetary(string="Taux journalier", required=True, default=0,
                                 help="Taux journalier pour ce profil", currency_field='currency_id')
    involvement = fields.Selection(INVOLVEMENT_TYPES, string="Implication", required=True, default='full',
                                   help="Niveau d'implication pour ce profil")
    involvement_percentage = fields.Float(string="% Implication", compute='_compute_involvement_percentage', store=True,
                                          help="Pourcentage d'implication pour ce profil")
    workload_days = fields.Float(string="Charge (Jours)", required=True, default=0,
                                 help="Nombre de jours ouvrés estimés pour ce profil")

    @api.onchange('role_id')
    def _onchange_role_id(self):
        """Set daily rate when role changes if it has a default value"""
        for record in self:
            if record.role_id and record.role_id.default_daily_rate:
                record.daily_rate = record.role_id.default_daily_rate

    @api.depends('involvement')
    def _compute_involvement_percentage(self):
        """Compute the involvement percentage based on the involvement selection"""
        percentages = {
            'quarter': 0.25,
            'half': 0.50,
            'three_quarter': 0.75,
            'full': 1.0
        }
        for record in self:
            record.involvement_percentage = percentages.get(record.involvement, 1.0)

    @api.constrains('involvement_percentage')
    def _check_involvement_percentage(self):
        """Ensure involvement percentage is between 1 and 100"""
        for record in self:
            if record.involvement_percentage < 0.01 or record.involvement_percentage > 1:
                raise models.ValidationError("Le pourcentage d'implication doit être compris entre 1 et 100.")

    @api.constrains('daily_rate')
    def _check_daily_rate(self):
        """Ensure daily rate is not negative"""
        for record in self:
            if record.daily_rate < 0:
                raise models.ValidationError("Le taux journalier ne peut pas être négatif.")

    @api.depends('project_id.company_id')
    def _compute_currency_id(self):
        for record in self:
            record.currency_id = record.project_id.company_id.currency_id or self.env.company.currency_id
