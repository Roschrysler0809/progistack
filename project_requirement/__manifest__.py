{
    'name': "Suivi Projet",
    'summary': "Module de suivi du projet",
    'description': """
        Permet de gérer et suivre le développement du projet.
    """,

    'author': "Progistack - Hadi Zorkot",
    'website': "https://www.progistack.com",

    'category': 'Project',
    'version': '0.2',
    'depends': ['base', 'analytic', 'project', 'contacts', 'hr', 'mail', 'sale', 'crm', 'sale_crm', 'sale_project',
                'hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'data/project_data.xml',
        'views/project_department_views.xml',
        'views/project_requirement_views.xml',
        'views/project_subrequirement_views.xml',
        'views/project_requirement_line_views.xml',
        'views/project_subrequirement_line_views.xml',
        'views/project_custom_requirement_line_views.xml',
        'views/project_custom_subrequirement_line_views.xml',
        'views/project_profile_line_views.xml',
        'views/project_department_lot_views.xml',
        'views/project_views.xml',
        'views/project_department_tab.xml',
        'views/project_task_views.xml',
        'views/project_task_gantt_view.xml',
        'views/hr_job_views.xml',
        'views/crm_lead_views.xml',
        'views/hr_timesheet_views.xml',
        'wizards/project_requirement_selection_views.xml',
        'views/project_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_requirement/static/src/js/requirement_line_field.js',
            'project_requirement/static/src/css/requirement_line_field.scss',
            'project_requirement/static/src/xml/requirement_line_field.xml',
        ],
    },
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
