# -*- coding: utf-8 -*-
{
    'name': 'Project Reporting',
    'version': '1.0',
    'summary': 'Générer des rapports de suivi pour les projets',
    'description': '''
        Ce module permet de générer des rapports de suivi pour les projets.
        Il fournit un assistant pour créer et automatiser la génération des rapports.
    ''',
    'category': 'Project',
    'author': 'Progistack - Hadi Zorkot',
    'website': 'https://www.progistack.com',
    'depends': ['project', 'mail', 'project_requirement'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/project_flash_report_line_views.xml',
        'views/project_tracking_report_line_views.xml',
        'views/project_update_mail_templates.xml',
        'views/project_update_views.xml',
        'wizards/project_update_wizard_views.xml',
        'views/project_menus.xml',
        'reports/project_flash_report.xml',
        'reports/project_flash_report_templates.xml',
    ],
    'demo': [],
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
