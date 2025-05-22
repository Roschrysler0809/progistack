# Common constants and methods for project-related models

# Selection fields
DEPARTMENT_TYPE_SELECTION = [
    ('custom', 'Custom'),
    ('standard', 'Standard'),
]

IMPLEMENTATION_CATEGORY_SELECTION = [
    ('integration', 'Intégration'),
    ('evolution', 'Evolution'),
]

ETUDE_CHIFFRAGE_CATEGORY_SELECTION = [
    ('billable', 'Facturé'),
    ('non_billable', 'Non facturé'),
]

PROJECT_TYPE_NEXT_STEP_SELECTION = [
    ('internal', 'Interne'),
    ('etude_chiffrage', 'Etude et chiffrage'),
    ('implementation', 'Implémentation'),
    ('maintenance', 'Maintenance et support'),
]


# Common methods for project-related models
def convert_next_step_to_project_type(next_step):
    """Convert the next_step selection value to the corresponding project_type value"""
    # Map of next_step values to project_type values
    conversion_map = {
        'etude_chiffrage': 'etude_chiffrage',
        'implementation': 'implementation',
    }

    if not next_step:
        return 'etude_chiffrage'  # Default value

    return conversion_map.get(next_step, 'etude_chiffrage')


def get_generic_department(env):
    """Get the generic department for evolution projects. Creates it if it doesn't exist."""
    generic_department = env['project.department'].search([('code', '=', 'generic')], limit=1)

    # If generic department doesn't exist, create it
    if not generic_department:
        generic_department = env['project.department'].create({
            'name': 'Général',
            'code': 'generic',
            'is_readonly': True,
        })

    return generic_department
