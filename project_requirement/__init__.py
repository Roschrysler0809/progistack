from . import models
from . import wizards


def post_init_hook(env):
    """
    Post-init hook to ensure the generic department exists.
    This is called when the module is installed.
    """
    from odoo import api, SUPERUSER_ID
    from .models.common_projects import get_generic_department

    # env = api.Environment(cr, SUPERUSER_ID, {})
    # Ensure generic department exists
    get_generic_department(env)
