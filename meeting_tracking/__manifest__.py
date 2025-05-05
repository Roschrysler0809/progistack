{
    'name': 'Suivi des Réunions',
    'summary': 'Suivi et gestion des réunions de projet',
    'description': '''
        Ce module étend les événements du calendrier pour suivre les réunions de projet
    ''',

    'author': 'Progistack - Hadi Zorkot',
    'website': 'https://www.progistack.com',

    'category': 'Project',
    'version': '1.0',
    'depends': ['base', 'calendar', 'project', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/calendar_event_views.xml',
        'views/project_views.xml',
        'views/project_menus.xml',
        'data/mail_template_data.xml',
    ],
    'license': 'LGPL-3',
}
