# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .common_projects import get_generic_department


class ProjectDepartmentLotWizard(models.TransientModel):
    _name = 'project.department.lot'
    _description = 'Lot de départements de projet'
    _order = 'lot_number asc'

    name = fields.Char(string='Lot')
    lot_number = fields.Integer(string='Numéro de lot', required=True, readonly=True)
    project_id = fields.Many2one('project.project', string='Projet', required=True)
    department_ids = fields.Many2many('project.department', string='Départements')
    mep_planned_date = fields.Date(string="Date MEP prévue", required=True)
    delivery_planned_date = fields.Date(string="Date Livraison prévue", required=True)
    available_department_ids = fields.Many2many('project.department',
                                                compute='_compute_available_department_ids',
                                                string='Départements disponibles')

