from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _
from .common_dates import (
    is_business_day,
    adjust_duration_by_workforce
)
from .common_projects import (
    DEPARTMENT_TYPE_SELECTION,
    IMPLEMENTATION_CATEGORY_SELECTION,
    ETUDE_CHIFFRAGE_CATEGORY_SELECTION,
    PROJECT_TYPE_NEXT_STEP_SELECTION,
    get_generic_department
)
from .common_requirements import (
    HOURS_PER_DAY
)


class Project(models.Model):
    _inherit = 'project.project'

    # Selection fields
    STAGE_SELECTION = [
        ('preparation', 'Préparation'),
        ('devis_created', 'Devis créé'),
        ('devis_validated', 'Devis validé'),
        ('project', 'Projet'),
    ]

    # Flags to indicate where the project was created from
    from_crm = fields.Boolean(string="Généré depuis CRM", default=False)
    from_etude_chiffrage = fields.Boolean(string="Généré depuis Etude et Chiffrage", default=False)

    # Determines if project requires devis steps
    requires_devis_steps = fields.Boolean(string="Nécessite création de devis",
                                          compute="_compute_requires_devis_steps",
                                          store=True,
                                          help="Détermine si le projet nécessite les étapes de création et validation de devis")

    # Reference to generated implementation project
    implementation_project_id = fields.Many2one('project.project', string="Projet", readonly=True, copy=False)
    show_implementation_project_button = fields.Boolean(string="Afficher le bouton du projet d'implémentation",
                                                        compute="_compute_show_implementation_project_button")

    # Messages
    department_tabs_readonly_message = fields.Char(compute="_compute_department_tabs_readonly_message", readonly=True)

    # Date conditions
    is_weekend_date = fields.Boolean(string="Date sur weekend", compute="_compute_is_weekend_date",
                                     help="Indique si la date de début projet tombe sur un weekend")
    is_end_date_invalid = fields.Boolean(compute='_compute_is_end_date_invalid')

    # Color index for visual distinction of project types
    project_type_color = fields.Integer(string="Couleur du type de projet", compute="_compute_project_type_color",
                                        store=True,
                                        help="Couleur utilisée pour distinguer visuellement les types de projets")

    # Project fields
    project_type = fields.Selection(PROJECT_TYPE_NEXT_STEP_SELECTION, string="Type de projet",
                                    required=True, tracking=True)
    department_type = fields.Selection(DEPARTMENT_TYPE_SELECTION, string="Suivi département",
                                       tracking=True)
    implementation_category = fields.Selection(IMPLEMENTATION_CATEGORY_SELECTION, string="Catégorie implementation", default=False, tracking=True)
    etude_chiffrage_category = fields.Selection(ETUDE_CHIFFRAGE_CATEGORY_SELECTION, string="Catégorie étude/chiffrage", tracking=True)
    department_ids = fields.Many2many('project.department', string="Département(s)",
                                      required=True)
    stage = fields.Selection(STAGE_SELECTION, string="Etape", default='preparation',
                             required=True, tracking=True)
    available_stages = fields.Selection(STAGE_SELECTION, string="Étapes disponibles",
                                        compute="_compute_available_stages",
                                        help="Liste des étapes disponibles en fonction du type de projet")

    # Devis generation fields
    devis_generated_by = fields.Many2one('res.users', string="Devis généré par", readonly=True, tracking=True)
    devis_generated_date = fields.Datetime(string="Devis généré le", readonly=True, tracking=True)

    # Devis validation fields
    devis_validated_by = fields.Many2one('res.users', string="Devis validé par", readonly=True, tracking=True)
    devis_validated_date = fields.Datetime(string="Devis validé le", readonly=True, tracking=True)

    # Project creation fields
    project_created_by = fields.Many2one('res.users', string="Projet créé par", readonly=True, tracking=True)
    project_created_date = fields.Datetime(string="Projet créé le", readonly=True, tracking=True)

    # Profile lines
    profile_line_ids = fields.One2many('project.profile.line', 'project_id', string="Profils")

    # Sale order fields
    sale_order_ids = fields.Many2many('sale.order', string="Tous les devis", readonly=True,
                                      default=lambda self: [(6, 0, [])])
    current_sale_order_id = fields.Many2one('sale.order', string="Devis", readonly=True,
                                            help="Dernier devis généré et actif")
    current_sale_order_state = fields.Char(string="État du devis actuel", compute="_compute_current_sale_order_state",
                                           store=True)
    all_devis_confirmed = fields.Boolean(string="Tous les devis sont confirmés",
                                         compute="_compute_project_state_from_devis",
                                         store=True)

    # Requirement lines
    requirement_line_ids = fields.One2many('project.requirement.line', 'project_id',
                                           string="Lignes d'exigence")

    # Custom requirement lines for evolution projects
    custom_requirement_line_ids = fields.One2many('project.custom.requirement.line', 'project_id',
                                                  string="Lignes d'exigence personnalisées")

    # Computed fields for department visibility and requirement lines
    department_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                                   string="Exigences par département",
                                                   compute='_compute_department_requirement_lines')

    # Computed fields for department-specific requirements
    achat_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                              string="Exigences Achat",
                                              compute='_compute_department_requirement_lines')
    vente_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                              string="Exigences Vente",
                                              compute='_compute_department_requirement_lines')
    finance_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                                string="Exigences Finance",
                                                compute='_compute_department_requirement_lines')
    rh_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                           string="Exigences RH",
                                           compute='_compute_department_requirement_lines')
    stock_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                              string="Exigences Stock",
                                              compute='_compute_department_requirement_lines')
    production_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                                   string="Exigences Production",
                                                   compute='_compute_department_requirement_lines')
    transverse_requirement_lines = fields.One2many('project.requirement.line', 'project_id',
                                                   string="Exigences Transverse",
                                                   compute='_compute_department_requirement_lines')

    # Computed fields for department-specific custom requirements
    custom_achat_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                     string="Exigences personnalisées Achat",
                                                     compute='_compute_department_custom_requirement_lines')
    custom_vente_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                     string="Exigences personnalisées Vente",
                                                     compute='_compute_department_custom_requirement_lines')
    custom_finance_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                       string="Exigences personnalisées Finance",
                                                       compute='_compute_department_custom_requirement_lines')
    custom_rh_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                  string="Exigences personnalisées RH",
                                                  compute='_compute_department_custom_requirement_lines')
    custom_stock_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                     string="Exigences personnalisées Stock",
                                                     compute='_compute_department_custom_requirement_lines')
    custom_production_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                          string="Exigences personnalisées Production",
                                                          compute='_compute_department_custom_requirement_lines')
    custom_transverse_requirement_lines = fields.One2many('project.custom.requirement.line', 'project_id',
                                                          string="Exigences personnalisées Transverse",
                                                          compute='_compute_department_custom_requirement_lines')

    # Boolean fields to indicate if departments are selected
    has_achat_department = fields.Boolean(string="Département Achat", compute="_compute_has_departments", store=True)
    has_vente_department = fields.Boolean(string="Département Vente", compute="_compute_has_departments", store=True)
    has_finance_department = fields.Boolean(string="Département Finance", compute="_compute_has_departments",
                                            store=True)
    has_rh_department = fields.Boolean(string="Département RH", compute="_compute_has_departments", store=True)
    has_stock_department = fields.Boolean(string="Département Stock", compute="_compute_has_departments", store=True)
    has_production_department = fields.Boolean(string="Département Production", compute="_compute_has_departments",
                                               store=True)
    has_transverse_department = fields.Boolean(string="Département Transverse", compute="_compute_has_departments",
                                               store=True)

    # Flag to determine if new requirements are available
    has_new_requirements = fields.Boolean(string="Nouvelles exigences disponibles",
                                          compute="_compute_has_new_requirements")

    # UI visibility flags
    show_insert_requirements_button = fields.Boolean(string="Afficher le bouton d'insertion des exigences",
                                                     compute="_compute_show_insert_requirements_button")
    show_insert_requirements_button = fields.Boolean(string="Afficher bouton insertion exigences",
                                                     compute="_compute_show_insert_requirements_button")
    show_implementation_project_button = fields.Boolean(string="Afficher bouton projet implémentation",
                                                        compute="_compute_show_implementation_project_button")
    show_profiles_tab = fields.Boolean(string="Afficher l'onglet Profils", compute="_compute_show_profiles_tab")
    show_requirements_tab = fields.Boolean(string="Afficher l'onglet Exigences",
                                           compute="_compute_show_requirements_tab")
    show_custom_requirements_tab = fields.Boolean(string="Afficher l'onglet Exigences personnalisées",
                                                  compute="_compute_show_custom_requirements_tab")
    show_generate_tasks_button = fields.Boolean(string="Afficher bouton génération tâches directe",
                                                compute="_compute_show_generate_tasks_button")
    is_department_type_readonly = fields.Boolean(string="Est-ce que le type de département est en lecture seule",
                                                 compute='_compute_is_department_type_readonly')

    # Field validation flags
    profiles_required = fields.Boolean(string="Profils requis",
                                       compute="_compute_profiles_required", store=True)
    requirements_required = fields.Boolean(string="Exigences requises",
                                           compute="_compute_requirements_required", store=True)
    project_requires_custom_requirements = fields.Boolean(string="Nécessite des exigences personnalisées",
                                                          compute="_compute_project_requires_custom_requirements",
                                                          store=True,
                                                          help="Indique si ce projet utilise des exigences personnalisées au lieu des exigences standards")
    custom_requirements_required = fields.Boolean(string="Exigences personnalisées requises",
                                                  compute="_compute_custom_requirements_required",
                                                  store=True,
                                                  help="Indique si ce projet nécessite des exigences personnalisées")
    regular_requirements_required = fields.Boolean(string="Exigences standards requises",
                                                   compute="_compute_regular_requirements_required",
                                                   store=True,
                                                   help="Indique si ce projet nécessite des exigences standards")

    # Profile workload validation fields
    profiles_workload_valid = fields.Boolean(string="Charge des profils valide",
                                             compute="_compute_profiles_workload_valid", store=False)
    profiles_workload_message = fields.Char(string="Message validation charge",
                                            compute="_compute_profiles_workload_valid", store=False)
    profiles_vs_requirements_workload_info = fields.Html(string="Info charge profils/exigences",
                                                         compute="_compute_profiles_vs_requirements_workload_info",
                                                         store=False)

    # Department lots fields
    lot_ids = fields.One2many('project.department.lot', 'project_id', string='Lots de départements')
    lot_count = fields.Integer(compute='_compute_lot_count', string='Nombre de lots')
    has_lots = fields.Boolean(compute='_compute_has_lots', string='A des lots définis', store=True)
    has_lots_with_departments = fields.Boolean(compute='_compute_has_lots_with_departments',
                                               string='A des lots avec départements', store=True)
    all_departments_assigned = fields.Boolean(compute='_compute_all_departments_assigned',
                                              string='Tous les départements sont assignés', store=True)

    # Flag to indicate if there are requirement lines
    has_requirement_lines = fields.Boolean(string="A des exigences standards",
                                           compute="_compute_has_requirement_lines",
                                           store=True)
    has_custom_requirement_lines = fields.Boolean(string="A des exigences personnalisées",
                                                  compute="_compute_has_custom_requirement_lines",
                                                  store=True)

    # Flag to indicate if this is an evolution project
    is_evolution_project = fields.Boolean(string="Est un projet d'évolution",
                                          compute="_compute_is_evolution_project",
                                          store=True,
                                          help="Indique si ce projet est de type implémentation avec catégorie évolution")

    # Available departments for selection
    available_department_ids = fields.Many2many('project.department',
                                                compute='_compute_available_department_ids',
                                                string="Départements disponibles")

    @api.model
    def default_get(self, fields_list):
        """Override default_get to set default values"""
        defaults = super(Project, self).default_get(fields_list)
        # Set allow_billable to True by default
        if 'allow_billable' in fields_list:
            defaults['allow_billable'] = True
        # Handle naming conventions for projects
        if defaults.get('name') and not self.env.context.get('crm_lead_id'):
            # Apply the naming convention using the helper method
            defaults['name'] = self._format_project_name(
                defaults['name'],
                defaults.get('project_type'),
                defaults.get('from_crm', False),
                defaults.get('from_etude_chiffrage', False)
            )
        # For other cases, force manual entry if not from CRM or etude_chiffrage
        elif not defaults.get('from_crm') and not defaults.get('from_etude_chiffrage'):
            defaults['name'] = False

        return defaults

    @api.model
    def _get_generic_department(self):
        """Get the generic department for evolution projects"""
        return get_generic_department(self.env)

    @api.model
    def _get_department_domain(self):
        """Return domain to filter out generic department for evolution projects only"""
        domain = []

        # Check if we're in an evolution project
        is_evolution = self.project_type == 'implementation' and self.implementation_category == 'evolution'

        # For evolution projects, we already set the generic department programmatically
        # and don't want to show it in the dropdown
        if is_evolution:
            # Get the generic department
            generic_department = self._get_generic_department()
            if generic_department:
                domain = [('id', '!=', generic_department.id)]

        return domain

    @api.model
    def _search_department_ids(self, operator, value):
        """Custom search method for department_ids to filter out generic department for evolution projects"""
        # Call standard search
        domain = self.env['project.department']._search([('name', operator, value)])

        # Add filter for generic department if needed
        if self.project_type == 'implementation' and self.implementation_category == 'evolution':
            generic_department = self._get_generic_department()
            if generic_department:
                domain = ['&', domain, ('id', '!=', generic_department.id)]

        return domain

    @api.depends('project_type', 'implementation_category')
    def _compute_is_evolution_project(self):
        """Compute whether this is an evolution project"""
        for project in self:
            project.is_evolution_project = (project.project_type == 'implementation' and
                                            project.implementation_category == 'evolution')

    @api.depends('date_start')
    def _compute_is_weekend_date(self):
        """Check if project start date falls on a weekend"""
        for project in self:
            project.is_weekend_date = (project.date_start and
                                       not is_business_day(project.date_start))

    @api.depends('date_start', 'date')
    def _compute_is_end_date_invalid(self):
        """Check if project end date is before start date"""
        for project in self:
            project.is_end_date_invalid = bool(
                project.date_start and project.date and project.date < project.date_start)

    @api.depends('stage', 'project_type', 'implementation_project_id')
    def _compute_department_tabs_readonly_message(self):
        """Compute the department_tabs_readonly_message field"""
        for project in self:
            if project.stage == 'project' and (
                    project.project_type != 'etude_chiffrage' or project.implementation_project_id):
                project.department_tabs_readonly_message = "Les exigences sont en lecture seule lorsque le projet est en phase 'Projet'"
            elif project.stage == 'project' and project.project_type == 'etude_chiffrage' and not project.implementation_project_id:
                project.department_tabs_readonly_message = "Les exigences peuvent être modifiées uniquement dans l'onglet 'Toutes les exigences'"
            else:
                project.department_tabs_readonly_message = "Les exigences peuvent être modifiées uniquement dans l'onglet 'Toutes les exigences'"

    @api.depends('project_type')
    def _compute_project_type_color(self):
        """Assigns a distinct color to each project type for better visualization"""
        for project in self:
            # Use color 3 (blue) for Etude et chiffrage
            if project.project_type == 'etude_chiffrage':
                project.project_type_color = 3
            # Use color 2 (green) for Implementation
            elif project.project_type == 'implementation':
                project.project_type_color = 2
            # Default color 0 (gray) for other types
            else:
                project.project_type_color = 0

    @api.depends('current_sale_order_id', 'current_sale_order_id.state')
    def _compute_current_sale_order_state(self):
        """Compute the state of the current sale order"""
        for record in self:
            if record.current_sale_order_id:
                record.current_sale_order_state = record.current_sale_order_id.state
            else:
                record.current_sale_order_state = False

    @api.depends('department_ids')
    def _compute_has_departments(self):
        """Compute boolean fields for each department"""
        for project in self:
            project.has_achat_department = any(d.code == 'achat' for d in project.department_ids)
            project.has_vente_department = any(d.code == 'commerciale' for d in project.department_ids)
            project.has_finance_department = any(d.code == 'finance' for d in project.department_ids)
            project.has_rh_department = any(d.code == 'rh' for d in project.department_ids)
            project.has_stock_department = any(d.code == 'stock' for d in project.department_ids)
            project.has_production_department = any(d.code == 'production' for d in project.department_ids)
            project.has_transverse_department = any(d.code == 'transverse' for d in project.department_ids)

    @api.depends('project_type', 'implementation_category')
    def _compute_available_department_ids(self):
        """
        Compute available departments for selection:
        - For evolution projects: ONLY include the generic department
        - For other projects: include all departments EXCEPT the generic department
        """
        for project in self:
            # Get all departments
            all_departments = self.env['project.department'].search([])
            generic_department = self._get_generic_department()

            # Logic is different based on project type
            if project.project_type == 'implementation' and project.implementation_category == 'evolution':
                # For evolution projects, ONLY the generic department is available
                if generic_department:
                    project.available_department_ids = generic_department
                else:
                    project.available_department_ids = self.env['project.department']
            else:
                # For all other projects, all departments EXCEPT the generic one are available
                if generic_department:
                    project.available_department_ids = all_departments.filtered(lambda d: d.id != generic_department.id)
                else:
                    project.available_department_ids = all_departments

    @api.depends('requirement_line_ids', 'requirement_line_ids.requirement_id.department_id')
    def _compute_department_requirement_lines(self):
        """Compute requirement lines for each department"""
        for record in self:
            # Use filtered() directly to assign department-specific requirement lines
            record.achat_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'achat')
            record.vente_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'commerciale')
            record.finance_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'finance')
            record.rh_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'rh')
            record.stock_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'stock')
            record.production_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'production')
            record.transverse_requirement_lines = record.requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'transverse')

    @api.depends('department_ids', 'custom_requirement_line_ids', 'custom_requirement_line_ids.department_id')
    def _compute_department_custom_requirement_lines(self):
        """Compute custom requirement lines for each department"""
        for record in self:
            # Use filtered() directly to assign department-specific custom requirement lines
            record.custom_achat_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'achat')
            record.custom_vente_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'commerciale')
            record.custom_finance_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'finance')
            record.custom_rh_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'rh')
            record.custom_stock_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'stock')
            record.custom_production_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'production')
            record.custom_transverse_requirement_lines = record.custom_requirement_line_ids.filtered(
                lambda line: line.department_id.code == 'transverse')

    @api.depends('department_ids', 'requirement_line_ids', 'requirement_line_ids.requirement_id')
    def _compute_has_new_requirements(self):
        """Determine if there are new requirements that can be inserted"""
        for project in self:
            # Only check if departments are selected
            if not project.department_ids:
                project.has_new_requirements = False
                continue

            # Find available requirements that are not already in the project
            existing_requirement_ids = project.requirement_line_ids.mapped('requirement_id.id')
            new_requirements_count = self.env['project.requirement'].search_count([
                ('department_id', 'in', project.department_ids.ids),
                ('id', 'not in', existing_requirement_ids)
            ])

            project.has_new_requirements = new_requirements_count > 0

    @api.depends('sale_order_ids', 'sale_order_ids.state')
    def _compute_project_state_from_devis(self):
        """
        Monitor the state of the current devis and update project stage accordingly.
        
        This method synchronizes the project state with the state of its current devis:
        - When devis is confirmed (state='sale'): Project moves to 'devis_validated' stage
        - When devis is canceled (state='cancel'): Project reverts to 'devis_created' stage
        """
        for project in self:
            # Skip processing if no sale orders or no current devis
            if not project.current_sale_order_id:
                continue

            # Process based on current devis state
            self._process_devis_state_change(project, project.current_sale_order_id)

    def _process_devis_state_change(self, project, devis):
        """Process project state changes based on devis state"""
        state = devis.state

        # Only process state changes for the current devis
        if project.current_sale_order_id and devis.id != project.current_sale_order_id.id:
            return

        # Handle confirmed devis
        if state == 'sale':
            # Get confirmation details from message history
            confirmation_data = self._get_devis_confirmation_data(devis)

            update_vals = {
                'devis_validated_by': confirmation_data['user_id'],
                'devis_validated_date': confirmation_data['date'],
            }

            # Only update the project stage if it's in "devis_created" state
            if project.stage == 'devis_created':
                update_vals['stage'] = 'devis_validated'
                # Clear subsequent stage data only when changing stage
                update_vals.update({
                    'project_created_by': False,
                    'project_created_date': False,
                })

            # Update project with the gathered values
            project.write(update_vals)

        # Handle canceled devis
        elif state == 'cancel':
            # If this is the current devis being canceled, clear the reference only if not in project stage
            if project.current_sale_order_id and project.current_sale_order_id.id == devis.id and project.stage != 'project':
                # Only reset timestamps when going back to preparation state
                if project.stage in ['devis_created', 'devis_validated']:
                    project.write({
                        'stage': 'preparation',
                        'current_sale_order_id': False,
                        # Clear all relevant timestamps and fields for consistency
                        'devis_generated_by': False,
                        'devis_generated_date': False,
                        'devis_validated_by': False,
                        'devis_validated_date': False,
                    })
                else:
                    # Just clear the current devis reference without resetting timestamps
                    project.current_sale_order_id = False

        return True

    def _get_devis_confirmation_data(self, devis):
        """Get user ID and timestamp for devis confirmation"""
        # Query message history to find who confirmed the order
        self.env.cr.execute("""
            SELECT create_uid, create_date 
            FROM mail_message 
            WHERE model = 'sale.order' 
            AND res_id = %s 
            AND body LIKE '%%state%%sale%%' 
            ORDER BY create_date DESC 
            LIMIT 1
        """, (devis.id,))
        result = self.env.cr.fetchone()

        # Return confirmation data (use current user/time if not found)
        return {
            'user_id': result[0] if result else self.env.user.id,
            'date': result[1] if result else fields.Datetime.now()
        }

    @api.depends('stage', 'from_etude_chiffrage', 'requirement_line_ids', 'project_type', 'has_new_requirements',
                 'implementation_project_id')
    def _compute_show_insert_requirements_button(self):
        """Compute whether to show the insert requirements button"""
        for record in self:
            # Don't show in project stage - except for etude_chiffrage without implementation
            if record.stage == 'project' and (
                    record.project_type != 'etude_chiffrage' or record.implementation_project_id):
                record.show_insert_requirements_button = False
            # Show when there are new requirements available and not in project stage
            elif record.has_new_requirements and record.stage in ['preparation', 'devis_created', 'devis_validated']:
                record.show_insert_requirements_button = True
            # Show in preparation, devis_created and devis_validated stages when no requirements
            elif not record.requirement_line_ids and record.stage in ['preparation', 'devis_created',
                                                                      'devis_validated']:
                record.show_insert_requirements_button = True
            # Special case: Show for etude_chiffrage in project stage without implementation project when there are new requirements
            elif record.stage == 'project' and record.project_type == 'etude_chiffrage' and not record.implementation_project_id and record.has_new_requirements:
                record.show_insert_requirements_button = True
            # Special case: Show for etude_chiffrage in project stage without implementation project when there are no requirements
            elif record.stage == 'project' and record.project_type == 'etude_chiffrage' and not record.implementation_project_id and not record.requirement_line_ids:
                record.show_insert_requirements_button = True
            else:
                record.show_insert_requirements_button = False

    @api.depends('implementation_project_id', 'project_type')
    def _compute_show_implementation_project_button(self):
        """Determine whether to show the button to view the implementation project"""
        for record in self:
            # Only show the button if:
            # 1. This is an etude_chiffrage project
            # 2. There is a linked implementation project
            record.show_implementation_project_button = (record.project_type == 'etude_chiffrage' and
                                                         record.implementation_project_id)

    def _recompute_subrequirements_complexity(self):
        """
        Recompute complexity for all subrequirement lines in the project.
        This ensures that complexity values are always up-to-date with the current thresholds.
        """
        for project in self:
            subreq_lines = self.env['project.subrequirement.line'].search([
                ('requirement_line_id.project_id', '=', project.id)
            ])
            if subreq_lines:
                # Force recompute of complexity based on current estimated_work_days values
                for line in subreq_lines:
                    line._compute_complexity()

    @api.depends('project_type')
    def _compute_show_profiles_tab(self):
        """Determine if the profiles tab should be shown based on project type"""
        for project in self:
            project.show_profiles_tab = project._project_requires_profiles()

    @api.depends('requirement_line_ids')
    def _compute_has_requirement_lines(self):
        for project in self:
            project.has_requirement_lines = bool(project.requirement_line_ids)

    @api.depends('custom_requirement_line_ids')
    def _compute_has_custom_requirement_lines(self):
        for project in self:
            project.has_custom_requirement_lines = bool(project.custom_requirement_line_ids)

    @api.depends('project_type', 'implementation_category')
    def _compute_show_requirements_tab(self):
        """
        Determine if the standard requirements tab should be shown based on project type.
        
        For evolution projects, we don't show the standard requirements tab.
        For all other projects, we show it based on the project type's settings.
        """
        for project in self:
            # Don't show for evolution projects
            if project.project_type == 'implementation' and project.implementation_category == 'evolution':
                project.show_requirements_tab = False
            else:
                # For other projects, determine based on project type
                project.show_requirements_tab = project._project_shows_requirements_tab()

    @api.depends('project_type', 'implementation_category')
    def _compute_project_requires_custom_requirements(self):
        """Determine if project should use custom requirements instead of standard requirements"""
        for project in self:
            # Evolution projects use custom requirements
            project.project_requires_custom_requirements = project.is_evolution_project

    @api.depends('project_requires_custom_requirements', 'project_type')
    def _compute_custom_requirements_required(self):
        """Determine if custom requirements are required for this project type"""
        for project in self:
            # Default to false
            project.custom_requirements_required = False

            # First check if project requires requirements at all
            if not project._project_requires_requirements():
                continue

            # Only enable for projects that use custom requirements and require requirements
            project.custom_requirements_required = project.project_requires_custom_requirements

    @api.depends('project_requires_custom_requirements', 'project_type')
    def _compute_regular_requirements_required(self):
        """Determine if regular requirements are required for this project type"""
        for project in self:
            # Default to false
            project.regular_requirements_required = False

            # First check if project requires requirements at all
            if not project._project_requires_requirements():
                continue

            # Enable for projects that don't use custom requirements
            project.regular_requirements_required = not project.project_requires_custom_requirements

    @api.depends('custom_requirements_required')
    def _compute_show_custom_requirements_tab(self):
        """Determine if the custom requirements tab should be shown"""
        for record in self:
            record.show_custom_requirements_tab = record.custom_requirements_required

    @api.depends('project_type')
    def _compute_profiles_required(self):
        """Determine if profiles are required for this project type"""
        for project in self:
            project.profiles_required = project._project_requires_profiles()

    @api.depends('project_type', 'implementation_category')
    def _compute_requirements_required(self):
        """Determine if requirements are required for this project type"""
        for project in self:
            # Validation is based on core business logic
            project.requirements_required = project._project_requires_requirements()

    @api.depends('profile_line_ids', 'profile_line_ids.workload_days', 'requirement_line_ids',
                 'requirement_line_ids.estimated_work_days', 'custom_requirement_line_ids',
                 'custom_requirement_line_ids.estimated_work_days', 'custom_requirements_required',
                 'regular_requirements_required')
    def _compute_profiles_workload_valid(self):
        """
        Verify that the sum of profile workloads doesn't exceed the total requirement workload.
        This validation only applies if there is at least one requirement line.
        """
        for project in self:
            # Default values - assume valid until proven otherwise
            project.profiles_workload_valid = True
            project.profiles_workload_message = False

            # Skip validation if no profiles
            if not project.profile_line_ids:
                continue

            # Determine which requirements to validate against based on project type
            if project.custom_requirements_required:
                # Projects using custom requirements
                requirement_lines = project.custom_requirement_line_ids
            else:
                # Other projects use standard requirements  
                requirement_lines = project.requirement_line_ids

            # Skip validation if no requirements to validate against
            if not requirement_lines:
                continue

            # Calculate total profile workload
            total_profile_workload = sum(project.profile_line_ids.mapped('workload_days'))

            # Calculate total requirements workload
            total_requirement_workload = sum(requirement_lines.mapped('estimated_work_days'))

            # Check if profile workload exceeds requirement workload
            # Allow for small rounding differences (0.01 days)
            if total_profile_workload > total_requirement_workload + 0.01:
                project.profiles_workload_valid = False
                # Format numbers: show as int if they have no decimal part
                formatted_profile_load = int(
                    total_profile_workload) if total_profile_workload.is_integer() else total_profile_workload
                formatted_req_load = int(
                    total_requirement_workload) if total_requirement_workload.is_integer() else total_requirement_workload
                project.profiles_workload_message = (
                    f"La charge des profils ({formatted_profile_load} jours) "
                    f"ne peut pas dépasser la charge des exigences ({formatted_req_load} jours)"
                )

    @api.depends('profile_line_ids.workload_days', 'requirement_line_ids.estimated_work_days',
                 'custom_requirement_line_ids.estimated_work_days', 'custom_requirements_required',
                 'regular_requirements_required')
    def _compute_profiles_vs_requirements_workload_info(self):
        """Compute the string showing current profile workload vs requirement workload."""
        for project in self:
            # Determine which requirements to use based on project type
            if project.custom_requirements_required:
                # Projects using custom requirements
                requirement_lines = project.custom_requirement_line_ids
            else:
                # Other projects use standard requirements
                requirement_lines = project.requirement_line_ids

            # Skip if no requirements
            if not requirement_lines:
                project.profiles_vs_requirements_workload_info = "Aucune exigence définie."
                continue

            # Skip if no profiles
            if not project.profile_line_ids:
                project.profiles_vs_requirements_workload_info = "Aucun profil défini."
                continue

            # Calculate the total workloads
            profile_workload = sum(project.profile_line_ids.mapped('workload_days'))
            requirement_workload = sum(requirement_lines.mapped('estimated_work_days'))

            # Format the numbers - show as int if no decimal part
            formatted_profile_workload = int(
                profile_workload) if profile_workload.is_integer() else f"{profile_workload:.2f}"
            formatted_requirement_workload = int(
                requirement_workload) if requirement_workload.is_integer() else f"{requirement_workload:.2f}"

            # Bold label and clean format
            project.profiles_vs_requirements_workload_info = f"<b>Charge assignée:</b> {formatted_profile_workload} / {formatted_requirement_workload} jours"

    @api.depends('lot_ids')
    def _compute_lot_count(self):
        for project in self:
            project.lot_count = len(project.lot_ids)

    @api.depends('lot_ids')
    def _compute_has_lots(self):
        for project in self:
            project.has_lots = len(project.lot_ids) > 0

    @api.depends('lot_ids', 'lot_ids.department_ids')
    def _compute_has_lots_with_departments(self):
        for project in self:
            project.has_lots_with_departments = any(lot.department_count > 0 for lot in project.lot_ids)

    @api.depends('lot_ids', 'lot_ids.department_ids', 'department_ids', 'is_evolution_project')
    def _compute_all_departments_assigned(self):
        """Compute whether all departments of the project are assigned to lots."""
        for project in self:
            if not project.department_ids:
                project.all_departments_assigned = False
                continue

            # Get all departments assigned to lots
            assigned_departments = project.lot_ids.mapped('department_ids')

            # Check if all project departments are in the assigned departments
            project.all_departments_assigned = all(dept in assigned_departments for dept in project.department_ids)

    @api.depends('project_type', 'implementation_category', 'stage', 'from_crm', 'from_etude_chiffrage')
    def _compute_is_department_type_readonly(self):
        """Determine if the department_type field should be readonly."""
        for project in self:
            readonly_due_to_stage = project.stage != 'preparation'
            readonly_due_to_origin = project.from_crm and not project.from_etude_chiffrage
            readonly_due_to_evolution = project.project_type == 'implementation' and project.implementation_category == 'evolution'

            project.is_department_type_readonly = readonly_due_to_stage or readonly_due_to_origin or readonly_due_to_evolution

    @api.depends('project_type', 'etude_chiffrage_category', 'implementation_category')
    def _compute_requires_devis_steps(self):
        """
        Determine if the project requires the devis creation and validation steps.
        """
        for project in self:
            # Default to requiring quotation steps
            requires_devis = True

            # Etude et chiffrage with Non Facturé category doesn't need quotation
            if project.project_type == 'etude_chiffrage' and project.etude_chiffrage_category == 'non_billable':
                requires_devis = False

            # You can add more conditions here for other project types
            # Example: if project.project_type == 'internal_project':
            #              requires_devis = False

            project.requires_devis_steps = requires_devis

    @api.depends('requires_devis_steps')
    def _compute_available_stages(self):
        """Calculate available stages based on quotation requirements"""
        for project in self:
            if project.requires_devis_steps:
                # All stages are available
                project.available_stages = False
            else:
                # For projects without devis steps, we need to use a valid selection value
                # The available_stages is a Selection field with the same options as stage
                # Set it to 'preparation' which is a valid selection value
                project.available_stages = 'preparation'

                # If project is already in an unavailable stage, set it to preparation
                if project.stage in ['devis_created', 'devis_validated']:
                    project.stage = 'preparation'

    @api.depends('stage', 'requires_devis_steps', 'profile_line_ids', 'requirement_line_ids',
                 'custom_requirement_line_ids', 'date_start', 'date',
                 'is_end_date_invalid', 'has_lots', 'all_departments_assigned',
                 'project_type', 'custom_requirements_required', 'regular_requirements_required')
    def _compute_show_generate_tasks_button(self):
        """Determine if the direct task generation button should be shown"""
        for project in self:
            # Only show for projects that don't require quotation steps and are in preparation stage
            show_button = (project.stage == 'preparation' and
                           not project.requires_devis_steps)

            # Don't show if project start date is not set
            if show_button and not project.date_start:
                show_button = False

            # Don't show if project end date is not set or invalid
            if show_button and (not project.date or project.is_end_date_invalid):
                show_button = False

            # Don't show if profiles are required but not set
            if show_button and project._project_requires_profiles() and not project.profile_line_ids:
                show_button = False

            # Check requirements using the specific boolean fields
            if show_button and project.custom_requirements_required and not project.custom_requirement_line_ids:
                show_button = False
            elif show_button and project.regular_requirements_required and not project.requirement_line_ids:
                show_button = False

            # Don't show if lots don't exist or not all departments are assigned to lots
            if show_button and not project.has_lots:
                show_button = False

            if show_button and not project.all_departments_assigned:
                show_button = False

            project.show_generate_tasks_button = show_button

    @api.constrains('stage', 'date_start')
    def _check_project_start_date(self):
        """Ensure project start date is set when stage is project"""
        for project in self:
            if project.stage == 'project' and not project.date_start:
                raise models.ValidationError("La date de début du projet est obligatoire lorsque le projet est généré.")

    @api.constrains('date_start', 'date')
    def _check_project_dates(self):
        """Ensure project end date is not before project start date"""
        for project in self:
            if project.date_start and project.date and project.date < project.date_start:
                raise models.ValidationError("La date de fin du projet ne peut pas être antérieure à la date de début.")

    @api.constrains('date_start')
    def _check_start_date_is_not_weekend(self):
        """Ensure project start date is not a weekend."""
        for project in self:
            if project.date_start and not is_business_day(project.date_start):
                raise models.ValidationError(
                    "La date de début du projet ne peut pas être un weekend. Veuillez choisir un jour ouvrable."
                )

    @api.constrains('date_start')
    def _check_start_date_is_not_weekend(self):
        """Ensure project start date is not a weekend."""
        for project in self:
            if project.date_start and not is_business_day(project.date_start):
                raise models.ValidationError(
                    "La date de début du projet ne peut pas être un weekend. Veuillez choisir un jour ouvrable."
                )

    @api.constrains('stage')
    def _check_lots_required(self):
        """Ensure projects have lots and all departments are assigned to lots when moving to 'project' stage."""
        for project in self:
            if project.stage == 'project':
                if not project.has_lots:
                    raise models.ValidationError(
                        "Vous devez créer au moins un lot pour ce projet avant de passer à l'étape 'Projet'."
                    )
                if not project.all_departments_assigned:
                    raise models.ValidationError(
                        "Tous les départements du projet doivent être assignés à un lot avant de passer à l'étape 'Projet'."
                    )

    @api.constrains('stage', 'requires_devis_steps')
    def _check_valid_stages(self):
        """Ensure projects without devis steps cannot enter devis stages"""
        for project in self:
            if not project.requires_devis_steps and project.stage in ['devis_created', 'devis_validated']:
                raise models.ValidationError("Ce type de projet ne peut pas passer par les étapes de devis.")

    @api.constrains('stage')
    def _check_lots_required(self):
        """Ensure projects have lots and all departments are assigned to lots when moving to 'project' stage."""
        for project in self:
            if project.stage == 'project':
                if not project.has_lots:
                    raise models.ValidationError(
                        "Vous devez créer au moins un lot pour ce projet avant de passer à l'étape 'Projet'."
                    )
                if not project.all_departments_assigned:
                    raise models.ValidationError(
                        "Tous les départements du projet doivent être assignés à un lot avant de passer à l'étape 'Projet'."
                    )
                if project.implementation_category == 'integration' and (not all(lot.delivery_planned_date for lot in project.lot_ids) or not all(lot.mep_planned_date for lot in project.lot_ids)):
                    raise models.ValidationError(
                        "Vous devez spécifier une date de livraison et une date de MEP pour chaque lot avant de passer à l'étape 'Projet'."
                    )

    @api.constrains('stage', 'requires_devis_steps')
    def _check_valid_stages(self):
        """Ensure projects without devis steps cannot enter devis stages"""
        for project in self:
            if not project.requires_devis_steps and project.stage in ['devis_created', 'devis_validated']:
                raise models.ValidationError("Ce type de projet ne peut pas passer par les étapes de devis.")

    @api.onchange('project_type')
    def _onchange_project_type(self):
        """Update name according to project type and handle default values for implementation projects"""
        # Set default values for implementation projects or clear fields for other project types
        if self.project_type == 'implementation':
            # Clear other project types fields
            self.etude_chiffrage_category = False
            # Set defaults for implementation projects
            # For evolution, force standard department type
            if self.implementation_category == 'evolution':
                self.department_type = 'standard'

                # Get the generic department
                generic_department = self._get_generic_department()

                # Set only the generic department
                if generic_department:
                    self.department_ids = [(6, 0, [generic_department.id])]

                    # Clear all departments from lots
                    if self.lot_ids:
                        for lot in self.lot_ids:
                            lot.department_ids = [(5, 0, 0)]  # Clear all departments

        elif self.project_type == 'etude_chiffrage':
            # Clear other project types fields
            self.department_type = False
            self.implementation_category = False
            # Set default for etude_chiffrage_category if not set
            if not self.etude_chiffrage_category:
                self.etude_chiffrage_category = 'billable'
        else:
            # Clear other project types fields
            self.department_type = False
            self.implementation_category = False
            self.etude_chiffrage_category = False

        # Skip if no name or special creation context
        if not self.name:
            return

        # Update the name based on the new project type
        self.name = self._format_project_name(
            self.name,
            self.project_type,
            self.from_crm,
            self.from_etude_chiffrage,
            self.implementation_category
        )

    @api.onchange('implementation_category')
    def _onchange_implementation_category(self):
        """Update project settings based on implementation category selection"""
        # Only proceed if this is an implementation project and a category is selected
        if self.project_type != 'implementation' or not self.implementation_category:
            return

        # Step 1: ALWAYS clear ALL departments first
        self.department_ids = [(5, 0, 0)]

        # Step 2: Also clear departments from all lots
        if self.lot_ids:
            for lot in self.lot_ids:
                lot.department_ids = [(5, 0, 0)]

        # Step 3: For evolution ONLY, set to generic department
        if self.implementation_category == 'evolution':
            # Get the generic department
            generic_department = self._get_generic_department()
            if generic_department:
                # Set ONLY the generic department
                self.department_ids = [(6, 0, [generic_department.id])]
                # Set department type to standard
                self.department_type = 'standard'

    @api.onchange('date_start')
    def _onchange_project_start_date(self):
        """
        Trigger warning when a weekend date is selected for the project start date.
        """
        # Check if date is a weekend and warn user
        if self.date_start and self.date_start.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return {
                'warning': {
                    'title': 'Date non ouvrée',
                    'message': 'La date de début sélectionnée tombe sur un weekend. '
                               'Veuillez choisir un jour ouvrable.'
                }
            }

        # Note: the _compute_planned_dates will be triggered via write method

    @api.onchange('date')
    def _onchange_project_end_date(self):
        """
        Trigger warning when end date is before start date.
        """
        if self.date and self.date_start and self.date < self.date_start:
            return {
                'warning': {
                    'title': 'Date de fin incorrecte',
                    'message': 'La date de fin du projet ne peut pas être antérieure à la date de début.'
                }
            }

    def action_clear_requirement_lines(self):
        """Clear all requirement lines for the project"""
        self.ensure_one()

        # Don't allow clearing requirements for projects in 'project' stage except etude_chiffrage without implementation
        if self.stage == 'project' and (self.project_type != 'etude_chiffrage' or self.implementation_project_id):
            raise models.ValidationError("Vous ne pouvez pas supprimer les exigences d'un projet en phase 'Projet'.")

        if self.requirement_line_ids:
            self.requirement_line_ids.unlink()
        return True

    def action_clear_custom_requirement_lines(self):
        """Clear all custom requirement lines for the project"""
        self.ensure_one()

        # Don't allow clearing custom requirements for projects in 'project' stage except etude_chiffrage without implementation
        if self.stage == 'project' and (self.project_type != 'etude_chiffrage' or self.implementation_project_id):
            raise models.ValidationError(
                "Vous ne pouvez pas supprimer les exigences personnalisées d'un projet en phase 'Projet'.")

        if self.custom_requirement_line_ids:
            self.custom_requirement_line_ids.unlink()
        return True

    def action_insert_missing_requirements(self):
        """
        Opens a wizard to select requirements to add to the project.
        """
        self.ensure_one()

        # Don't allow inserting requirements for projects in 'project' stage except etude_chiffrage without implementation
        if self.stage == 'project' and (self.project_type != 'etude_chiffrage' or self.implementation_project_id):
            raise models.ValidationError("Vous ne pouvez pas ajouter d'exigences à un projet en phase 'Projet'.")

        if not self.department_ids:
            return

        # Open the requirements selection wizard
        return {
            'name': 'Sélectionner les exigences à ajouter',
            'type': 'ir.actions.act_window',
            'res_model': 'project.requirement.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': 'project.project'},
        }

    def action_insert_all_requirements(self):
        """
        Auto-populate requirements (exigences) based on selected departments.
        Only adds requirements that aren't already in the project.
        Clears requirement lines for departments that are no longer selected.
        Does not modify existing requirement lines to preserve manual changes.
        """
        self.ensure_one()

        # Don't allow inserting requirements for projects in 'project' stage except etude_chiffrage without implementation
        if self.stage == 'project' and (self.project_type != 'etude_chiffrage' or self.implementation_project_id):
            raise models.ValidationError("Vous ne pouvez pas ajouter d'exigences à un projet en phase 'Projet'.")

        if not self.department_ids:
            return

        # Get all requirements for selected departments
        domain = [('department_id', 'in', self.department_ids.ids)]
        requirements = self.env['project.requirement'].search(domain, order='sequence, id')

        # Find requirements to add and calculate next order number
        max_order = 0
        if self.requirement_line_ids:
            max_order = max(self.requirement_line_ids.mapped('order') or [0])

        # Remove requirement lines for departments no longer selected
        # Context: prevents auto-subrequirements and marks as coming from insertion
        department_ids = self.department_ids.ids
        to_remove = self.requirement_line_ids.filtered(
            lambda r: r.requirement_id.department_id.id not in department_ids
        )
        if to_remove:
            to_remove.with_context(
                skip_auto_subrequirements=True,
                from_requirements_insertion=True
            ).unlink()

        # Get the existing requirements after potential removals
        existing_requirement_ids = self.requirement_line_ids.mapped('requirement_id.id')

        # Add only missing requirements, never modify existing ones
        for requirement in requirements:
            # Skip if requirement already exists (respect manual modifications)
            if requirement.id in existing_requirement_ids:
                continue

            # Create new requirement line
            max_order += 1

            # Prepare values for requirement line
            req_line_vals = {
                'project_id': self.id,
                'requirement_id': requirement.id,
                'type': requirement.type,
                'order': max_order,
            }

            # Create requirement line - allow subrequirements to be created only once during creation
            # Explicitly set skip_auto_subrequirements=False to ensure we create subrequirements
            # from_requirements_insertion=True to indicate this comes from auto-insertion
            self.env['project.requirement.line'].with_context(
                skip_auto_subrequirements=False,
                from_requirements_insertion=True
            ).create(req_line_vals)

        # Refresh the computation of available requirements properly
        self.invalidate_recordset(['has_new_requirements'])

        return True

    def action_view_latest_devis(self):
        """Open the current active devis related to this project"""
        self.ensure_one()

        # Only show the current devis if it exists
        if not self.current_sale_order_id:
            return {'type': 'ir.actions.act_window_close'}

        return {
            'name': 'Devis du projet',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.current_sale_order_id.id,
            'context': {'default_partner_id': self.partner_id.id},
        }

    def action_view_all_devis(self):
        """Open all the sale orders (devis) linked to this project always in list view"""
        self.ensure_one()

        if not self.sale_order_ids:
            return {'type': 'ir.actions.act_window_close'}

        # Always show all devis in list view, even if there's only one
        return {
            'name': 'Tous les devis',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
            'context': {'default_partner_id': self.partner_id.id},
        }

    def _calculate_average_daily_rate(self):
        """
        Calculate average daily rate using the formula:
        Average daily rate = sum(daily_rate * involvement_percentage) / number of profiles
        """
        total_weighted_rate = 0
        total_profiles = len(self.profile_line_ids)

        if total_profiles > 0:
            for profile in self.profile_line_ids:
                total_weighted_rate += profile.daily_rate * profile.involvement_percentage

            avg_daily_rate = total_weighted_rate / total_profiles
        else:
            avg_daily_rate = 0

        return avg_daily_rate

    def action_generate_devis(self):
        """Generate quotation for the project based on requirements and profiles"""
        self.ensure_one()

        # Check if there's a current devis that's not canceled
        if self.current_sale_order_id and self.current_sale_order_id.state != 'cancel':
            raise models.ValidationError(
                "Impossible de générer un nouveau devis car un devis actif existe déjà. \n"
                "Vous devez d'abord annuler le devis existant."
            )

        # Check if the project has a client
        if not self.partner_id:
            raise models.ValidationError("Le projet doit avoir un client pour générer un devis.")

        # Check if departments are selected
        if not self.department_ids:
            raise models.ValidationError("Veuillez sélectionner au moins un département pour générer un devis.")

        # Check if there are profile lines for projects that need them
        if not self.profile_line_ids and self._project_requires_profiles():
            raise models.ValidationError(
                "Veuillez définir au moins un profil avec un taux journalier pour générer un devis.")

        # Determine which requirements to use based on required type
        if self.custom_requirements_required:
            # Projects that require custom requirements
            requirement_lines = self.custom_requirement_line_ids
        else:
            # Projects that require standard requirements
            requirement_lines = self.requirement_line_ids

        # Check if there are requirement lines for projects that need them
        if self._project_requires_requirements() and not requirement_lines:
            if self.custom_requirements_required:
                raise models.ValidationError(
                    "Veuillez définir au moins une exigence personnalisée pour générer un devis.")
            else:
                raise models.ValidationError("Veuillez définir au moins une exigence pour générer un devis.")

        # Create sale order
        SaleOrder = self.env['sale.order']
        order_vals = {
            'partner_id': self.partner_id.id,
            'client_order_ref': self.name,
        }
        sale_order = SaleOrder.create(order_vals)

        # Get departments associated with this project
        departments = self.department_ids

        # Initialize Classes
        Product = self.env['product.product']
        SaleOrderLine = self.env['sale.order.line']

        # For Etude et chiffrage, generate one line per department
        if self.project_type == 'etude_chiffrage':
            # Get the unit of measure for units
            UoM = self.env['uom.uom']
            uom_unit = UoM.search([('name', 'ilike', 'unité')], limit=1)
            if not uom_unit:
                uom_unit = UoM.search([('name', 'ilike', 'unit')], limit=1)

            # Get the product for Cadrage
            atelier_product = Product.search([('name', '=', 'Cadrage')], limit=1)
            if not atelier_product:
                # Create the product if it doesn't exist
                product_vals = {
                    'name': 'Cadrage',
                    'type': 'service',
                    'invoice_policy': 'order',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'taxes_id': [(6, 0, [])],  # Ensure no taxes are applied at product level
                    'supplier_taxes_id': [(6, 0, [])],  # Ensure no purchase taxes applied
                    'list_price': 1000000.0,  # Set initial price to 1,000,000
                }

                # Only set UoM if we found one (handles case where UoM module might be disabled)
                if uom_unit:
                    product_vals.update({
                        'uom_id': uom_unit.id,
                        'uom_po_id': uom_unit.id,
                    })

                atelier_product = Product.create(product_vals)

            # Create a section and line for each department selected in the project
            for department in departments:
                # First create a section line with the department name
                section_line_vals = {
                    'order_id': sale_order.id,
                    'display_type': 'line_section',
                    'name': department.name,
                }
                SaleOrderLine.create(section_line_vals)

                # Then create a product line for the workshop
                line_vals = {
                    'order_id': sale_order.id,
                    'product_id': atelier_product.id,
                    'name': "Etude et chiffrage",
                    'product_uom_qty': 1,
                    'price_unit': atelier_product.list_price,
                }

                # Only set product_uom if we found one
                if uom_unit:
                    line_vals['product_uom'] = uom_unit.id

                SaleOrderLine.create(line_vals)
        else:
            # Get the unit of measure for days
            UoM = self.env['uom.uom']
            uom_day = UoM.search([('name', 'ilike', 'jour')], limit=1)
            if not uom_day:
                uom_day = UoM.search([('name', 'ilike', 'day')], limit=1)

            # Implementation projects - create lines based on requirements
            # Get the product for requirements
            exigence_product = Product.search([('name', '=', 'Implémentation')], limit=1)
            if not exigence_product:
                # Create the product if it doesn't exist
                product_vals = {
                    'name': 'Implémentation',
                    'type': 'service',
                    'invoice_policy': 'order',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'taxes_id': [(6, 0, [])],  # Ensure no taxes are applied at product level
                    'supplier_taxes_id': [(6, 0, [])],  # Ensure no purchase taxes applied
                }

                # Only set UoM if we found one (handles case where UoM module might be disabled)
                if uom_day:
                    product_vals.update({
                        'uom_id': uom_day.id,
                        'uom_po_id': uom_day.id,
                    })

                exigence_product = Product.create(product_vals)

            # Calculate average daily rate once for all lines
            avg_daily_rate = self._calculate_average_daily_rate()

            for department in departments:
                # Use proper requirements based on project type
                if self.custom_requirements_required:
                    req_lines = self.custom_requirement_line_ids.filtered(lambda r: r.department_id.id == department.id)
                else:
                    # For other project types, use standard requirements
                    req_lines = self.requirement_line_ids.filtered(lambda r: r.department_id.id == department.id)

                if not req_lines:
                    continue

                # Add section for department
                section_line_vals = {
                    'order_id': sale_order.id,
                    'display_type': 'line_section',
                    'name': department.name,
                }
                SaleOrderLine.create(section_line_vals)

                # For each requirement line, calculate average daily rate and create sale order line
                for req_line in req_lines:
                    if req_line.estimated_work_days <= 0:
                        continue

                    # Use appropriate name/description based on requirement type
                    if self.custom_requirements_required:
                        # Use custom requirement name
                        line_description = req_line.name
                    else:
                        # Use standard requirement description or name
                        line_description = req_line.description if req_line.description else req_line.requirement_id.name

                    # Create sale order line for this requirement
                    line_vals = {
                        'order_id': sale_order.id,
                        'product_id': exigence_product.id,
                        'name': line_description,
                        'product_uom_qty': req_line.estimated_work_days,
                        'price_unit': avg_daily_rate,
                    }

                    # Only set product_uom if we found one
                    if uom_day:
                        line_vals['product_uom'] = uom_day.id

                    SaleOrderLine.create(line_vals)

        # Store sale order in a variable to ensure it's loaded properly
        created_order = self.env['sale.order'].browse(sale_order.id)

        # Update fields in a single write operation
        # Add the new devis to existing ones instead of replacing
        vals = {
            'sale_order_ids': [(4, created_order.id, 0)],  # Append the new devis to existing ones
            'current_sale_order_id': created_order.id,  # Set as the current active devis
            'stage': 'devis_created',
            'devis_generated_by': self.env.user.id,
            'devis_generated_date': fields.Datetime.now(),
            # Clear future state timestamps
            'devis_validated_by': False,
            'devis_validated_date': False,
            'project_created_by': False,
            'project_created_date': False,
        }

        # Update records in a fresh environment to avoid caching issues
        self.env['project.project'].browse(self.id).sudo().write(vals)

        # Ensure the cache is cleared
        self.env.cr.commit()

        # Return an action to open the newly created sale order
        return {
            'name': 'Devis du projet',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': created_order.id,
            'context': {'default_partner_id': self.partner_id.id},
        }

    def action_cancel_devis(self):
        """
        Cancel the current devis, clear all related timestamps and references,
        and return the project to preparation state.
        """
        self.ensure_one()

        # Check if we have a current devis to cancel
        if not self.current_sale_order_id:
            raise models.ValidationError("Aucun devis à annuler.")

        # Get the current devis
        current_devis = self.current_sale_order_id

        # Cancel the devis if it's in a state that can be canceled
        if current_devis.state in ['draft', 'sent', 'sale']:
            try:
                current_devis.action_cancel()
            except Exception as e:
                raise models.ValidationError(f"Erreur lors de l'annulation du devis: {str(e)}")

        # Only revert to preparation stage if project is in devis_created or devis_validated stages
        if self.stage in ['devis_created', 'devis_validated']:
            # Update project fields
            self.write({
                'stage': 'preparation',
                # Clear current devis reference
                'current_sale_order_id': False,
                # Clear devis generation fields
                'devis_generated_by': False,
                'devis_generated_date': False,
                # Clear devis validation fields
                'devis_validated_by': False,
                'devis_validated_date': False,
            })
        else:
            # Just clear the current devis reference without resetting timestamps
            self.current_sale_order_id = False

        return True

    def action_return_to_preparation(self):
        """
        Return project from 'devis_created' back to 'preparation' state.
        This resets the devis generation fields but keeps the existing devis in the database.
        """
        self.ensure_one()

        # Check that the project is in the correct state
        if self.stage != 'devis_created':
            raise models.ValidationError("Seuls les projets en état 'Devis créé' peuvent être remis en préparation.")

        # Update project state
        self.write({
            'stage': 'preparation',
            # Clear devis generation fields
            'devis_generated_by': False,
            'devis_generated_date': False,
            # We're keeping the sale_order_ids reference to maintain history
        })

        return True

    def action_validate_devis(self):
        """
        Validate devis action - trigger the confirmation of the current devis
        """
        self.ensure_one()

        # Check if there is a current devis to validate
        if not self.current_sale_order_id:
            raise models.ValidationError("Aucun devis actif à valider. Veuillez d'abord générer un devis.")

        # Get the current devis to validate
        current_devis = self.current_sale_order_id

        # Check if the current devis can be confirmed
        if current_devis.state not in ['draft']:
            raise models.ValidationError(
                f"Impossible de valider le devis {current_devis.name} car son état ({current_devis.state}) ne permet pas la confirmation."
            )

        # Try to confirm the devis
        try:
            current_devis.action_confirm()
        except Exception as e:
            raise models.ValidationError(f"Erreur lors de la confirmation du devis {current_devis.name}: {str(e)}")

        # Force recomputation of project state based on devis state
        self._compute_project_state_from_devis()

        # Check if the devis is now confirmed
        if current_devis.state != 'sale':
            raise models.ValidationError(f"Le devis {current_devis.name} n'a pas pu être confirmé correctement.")

        # Update the project state if not already done
        if self.stage != 'devis_validated':
            # Get the user who confirmed the order
            self.env.cr.execute("""
                SELECT create_uid, create_date 
                FROM mail_message 
                WHERE model = 'sale.order' 
                AND res_id = %s 
                AND body LIKE '%%state%%sale%%' 
                ORDER BY create_date DESC 
                LIMIT 1
            """, (current_devis.id,))
            result = self.env.cr.fetchone()

            confirmation_user_id = result[0] if result else self.env.user.id
            confirmation_date = result[1] if result else fields.Datetime.now()

            self.write({
                'stage': 'devis_validated',
                'devis_validated_by': confirmation_user_id,
                'devis_validated_date': confirmation_date,
                # Clear future state timestamps
                'project_created_by': False,
                'project_created_date': False,
            })

        return True

    def action_create_implementation_project(self):
        """
        Create an implementation project from the current project.
        Used to convert an 'etude_chiffrage' project into an implementation project.
        This method creates a duplicate project with type 'implementation'.
        """
        self.ensure_one()

        if not self.date_start:
            raise models.ValidationError("La date de début du projet est obligatoire pour générer le projet.")

        # Validate that the project start date is not a weekend
        if self.date_start.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            raise models.ValidationError(
                "La date de début du projet ne peut pas être un weekend. Veuillez choisir un jour ouvrable."
            )

        # Check if there are profile lines for projects that need them
        if not self.profile_line_ids and self._project_requires_profiles():
            raise models.ValidationError("Il doit y avoir au moins un profil défini pour générer le projet.")

        # Default implementation category
        # TODO: make this a parameter to determine which category to use for the implementation project
        implementation_category = 'integration'

        # Format the name with the implementation suffix directly
        formatted_name = self._format_project_name(
            self.name,  # Already clean name without any suffix
            'implementation',
            False,
            self.project_type == 'etude_chiffrage',  # Coming from etude_chiffrage
            implementation_category
        )

        # Create a duplicate project with all fields
        new_project = self.copy({
            'name': formatted_name,
            'project_type': 'implementation',
            'department_type': 'standard' if implementation_category == 'evolution' else False,
            'implementation_category': implementation_category,
            'stage': 'preparation',
            'project_created_by': False,
            'project_created_date': False,
            'date_start': False,
            'date': False,
            'department_ids': [(6, 0, self.department_ids.ids)],
            'partner_id': self.partner_id.id,
            # Clear all devis references and timestamps
            'sale_order_ids': [(5, 0, 0)],  # Clear all sale orders
            'current_sale_order_id': False,
            'current_sale_order_state': False,
            'devis_generated_by': False,
            'devis_generated_date': False,
            'devis_validated_by': False,
            'devis_validated_date': False,
            # Set flag if source project is etude_chiffrage
            'from_etude_chiffrage': self.project_type == 'etude_chiffrage',
            # Don't copy tasks
            'tasks': False,
            'task_ids': [(5, 0, 0)],
        })

        # Copy requirement lines with their subrequirement lines
        # 1. Create requirement lines without auto-generating subrequirements
        # 2. Manually copy each subrequirement with exact values
        # This ensures we get a perfect copy without generating default subrequirements
        for req_line in self.requirement_line_ids:
            # First create the requirement line with a context to skip auto-creation of subrequirements
            new_req_line = self.env['project.requirement.line'].with_context(skip_auto_subrequirements=True).create({
                'project_id': new_project.id,
                'requirement_id': req_line.requirement_id.id,
                'order': req_line.order,
                'description': req_line.description,
                'besoins': req_line.besoins,
                'challenges': req_line.challenges,
                'solutions': req_line.solutions,
            })

            # Then copy all subrequirement lines with their exact values
            for subreq_line in req_line.subrequirement_line_ids:
                self.env['project.subrequirement.line'].create({
                    'requirement_line_id': new_req_line.id,
                    'subrequirement_id': subreq_line.subrequirement_id.id,
                    'estimated_work_days': subreq_line.estimated_work_days,
                    'complexity': subreq_line.complexity,
                })

        # Copy profile lines
        for profile_line in self.profile_line_ids:
            profile_line.copy({
                'project_id': new_project.id,
            })

        # Copy lot lines
        for lot_line in self.lot_ids:
            lot_line.copy({
                'project_id': new_project.id,
            })

        # Update stage of the original project and set the reference to the implementation project
        self.write({
            'stage': 'project',
            'project_created_by': self.env.user.id,
            'project_created_date': fields.Datetime.now(),
            'implementation_project_id': new_project.id,
        })

        # Open the new project
        return {
            'name': 'Projet implémentation',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': new_project.id,
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }

    def action_view_implementation_project(self):
        """Open the implementation project generated from this project"""
        self.ensure_one()

        if not self.implementation_project_id:
            return {'type': 'ir.actions.act_window_close'}

        return {
            'name': 'Projet d\'implémentation',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.implementation_project_id.id,
            'target': 'current',
        }

    def action_create_lot(self):
        """Create a new lot for this project"""
        self.ensure_one()

        # Get the next lot number
        DepartmentLot = self.env['project.department.lot']
        next_lot_number = DepartmentLot.with_context(default_project_id=self.id)._get_next_lot_number()

        # Create a new lot with the determined number
        new_lot = DepartmentLot.create({
            'project_id': self.id,
            'lot_number': next_lot_number,
        })

        # Return without refreshing the page
        return True

    def action_add_custom_requirement_line(self):
        """Create a new custom requirement line for the project"""
        self.ensure_one()

        # For evolution projects, always use the generic department
        if self.project_type == 'implementation' and self.implementation_category == 'evolution':
            default_department = self._get_generic_department()
        else:
            # Get the departments for context and use the first one as default
            departments = self.department_ids
            default_department = departments and departments[0] or False

        # Set a context that the form view will use to properly set default values
        ctx = {
            'default_project_id': self.id,
            'default_department_id': default_department and default_department.id or False,
            'hide_project': True,
            # Add project type and implementation category to context
            'default_project_type': self.project_type,
            'default_implementation_category': self.implementation_category,
            'active_id': self.id,  # Add active_id to ensure proper context
            'active_model': 'project.project',  # Add active_model to ensure proper context
            'form_view_initial_mode': 'edit',  # Ensure form opens in edit mode
        }

        return {
            'name': _("Nouvelle exigence personnalisée"),
            'type': 'ir.actions.act_window',
            'res_model': 'project.custom.requirement.line',
            'view_mode': 'form',
            'view_id': self.env.ref('project_requirement.view_project_custom_requirement_line_form').id,
            'target': 'new',
            'context': ctx,
            'flags': {'mode': 'edit'},  # Ensure form opens in edit mode
        }

    def action_create_tasks(self):
        """Generate project tasks directly based on profile lines and requirements"""
        self.ensure_one()

        # Ensure project has stages before generating tasks
        self._ensure_project_stages()

        # Don't allow task creation without appropriate requirements
        if self.custom_requirements_required and not self.custom_requirement_line_ids:
            raise models.ValidationError(
                "Veuillez d'abord ajouter des exigences personnalisées avant de générer les tâches.")
        elif self.regular_requirements_required and not self.requirement_line_ids:
            raise models.ValidationError(
                "Veuillez d'abord ajouter des exigences avant de générer les tâches.")

        # Verify lots exist and all departments are assigned to lots
        if not self.has_lots:
            raise models.ValidationError(
                "Veuillez d'abord créer des lots pour les départements avant de générer les tâches.")

        if not self.all_departments_assigned:
            raise models.ValidationError(
                "Veuillez assigner tous les départements du projet à des lots avant de générer les tâches.")

        if not self.date_start:
            raise models.ValidationError("La date de début du projet est obligatoire pour générer les tâches.")

        # Validate that the project start date is not a weekend
        if self.date_start.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            raise models.ValidationError(
                "La date de début du projet ne peut pas être un weekend. Veuillez choisir un jour ouvrable.")

        # Check if there are profile lines for projects that need them
        if not self.profile_line_ids and self._project_requires_profiles():
            raise models.ValidationError("Il doit y avoir au moins un profil défini pour générer les tâches.")

        # Check if the total profile workload doesn't exceed the total requirement workload
        if not self.profiles_workload_valid:
            raise UserError(self.profiles_workload_message)

        # Different process based on project type
        if self.project_type == 'etude_chiffrage':
            # For Etude et chiffrage projects, create one task per department
            # and gather subrequirements from the library
            # Return the action directly to open the task view
            return self._create_etude_chiffrage_tasks()
        else:
            # For implementation projects, use the existing logic with requirements
            # Return the action directly to open the task view
            return self._create_implementation_tasks()

    def _ensure_project_stages(self):
        """Ensure project has the required stages before generating tasks"""
        self.ensure_one()
        self._apply_default_task_types()

    def _apply_default_task_types(self):
        """Apply default task stages to the project"""
        self.ensure_one()

        # Skip if project already has stages
        if self.type_ids:
            return

        # Get the task types from project_data.xml
        task_types = []

        # Get all stages defined in project_data.xml
        stages = [
            'project_task_type_todo',
            'project_task_type_in_progress',
            'project_task_type_done',
            'project_task_type_canceled'
        ]

        for stage_xml_id in stages:
            stage = self.env.ref(f'project_requirement.{stage_xml_id}', raise_if_not_found=True)
            task_types.append(stage)

        # Sort stages by sequence
        task_types.sort(key=lambda x: x.sequence)
        self.type_ids = [(6, 0, [t.id for t in task_types])]

    def _create_etude_chiffrage_tasks(self):
        """
        Create tasks for "Etude et chiffrage" projects.
        One task is generated for each department.
        """
        # Ensure project has the required stages
        self._ensure_project_stages()

        # Check if start date is set
        if not self.date_start:
            raise models.ValidationError("La date de début du projet est obligatoire pour générer les tâches.")

        # Calculate workforce factor for adjusted durations
        workforce_factor = self._calculate_workforce_factor()

        # Validate that we have stages
        if not self.type_ids:
            raise models.ValidationError("Aucune étape de tâche n'est définie pour ce projet.")

        # Get the first stage from project type_ids
        first_stage = self.type_ids[0]

        tasks = []

        # Create one task per department
        for department in self.department_ids:
            # Create the main task for the department
            task_name = f"Atelier de cadrage: {department.name}"

            # Calculate work days (skipping weekends)
            # Default duration for department task is 7 days, adjusted by workforce
            department_duration = adjust_duration_by_workforce(7, workforce_factor)

            task_vals = {
                'name': task_name,
                'project_id': self.id,
                'partner_id': self.partner_id.id if self.partner_id else False,
                'stage_id': first_stage.id,  # Always set the first stage
                'user_ids': [(5, 0, 0)],  # Clear all assigned users
            }

            # Create task with sudo to avoid potential permission issues
            task = self.env['project.task'].sudo().create(task_vals)
            tasks.append(task.id)

            # Find all subrequirements in the library that match:
            # - Same department
            # - project_type = "etude_chiffrage"
            # domain = [
            #     ('department_id', '=', department.id),
            #     ('project_type', '=', 'etude_chiffrage')
            # ]
            # 
            # subrequirements = self.env['project.subrequirement'].search(
            #     domain, order='sequence, id'
            # )
            #
            # Subtask generation code commented out - Can be re-enabled if subtask functionality is needed again
            # Create subtasks for each matching subrequirement
            # subtask_sequence = 0
            # for subreq in subrequirements:
            #     subtask_sequence += 1
            #     subtask_name = f"{department.name} - {subreq.description}"
            # 
            #     # Calculate end date for subtask, with proper business day handling
            #     # Adjust duration based on workforce factor
            #     subreq_days = subreq.estimated_work_days or 1
            #     adjusted_duration = adjust_duration_by_workforce(subreq_days, workforce_factor)
            #     subtask_end_date = add_working_days(self.date_start, adjusted_duration)
            # 
            #     # Convert to datetime with business hours
            #     subtask_start_datetime = datetime_with_business_hour(self.date_start, START_WORK_TIME)
            #     subtask_end_datetime = datetime_with_business_hour(subtask_end_date, END_WORK_TIME)
            # 
            #     subtask_vals = {
            #         'name': subtask_name,
            #         'parent_id': task.id,
            #         'project_id': self.id,
            #         'partner_id': self.partner_id.id,
            #         'user_ids': [(6, 0, user_ids)],
            #         'planned_date_begin': subtask_start_datetime,
            #         'date_deadline': subtask_end_datetime,
            #         'sequence': subtask_sequence,
            #     }
            # 
            #     self.env['project.task'].sudo().create(subtask_vals)

        # Update project state
        if tasks:
            self.write({
                'stage': 'project',
                'project_created_by': self.env.user.id,
                'project_created_date': fields.Datetime.now()
            })

            # Return action to view tasks
            action = self.env['ir.actions.act_window'].sudo()._for_xml_id('project.action_view_task')
            action.update({
                'domain': [('id', 'in', tasks)],
                'context': {'default_project_id': self.id}
            })
            return action
        else:
            raise models.ValidationError(
                "Aucune tâche n'a été générée. Vérifiez que des départements ont bien été sélectionnés.")

    def _create_implementation_tasks(self):
        """
        Generate project tasks based on requirements for implementation projects.
        
        For projects using custom requirements, tasks are created from custom requirement lines.
        For other projects, tasks are created from standard requirement lines.
        """
        self.ensure_one()

        # Ensure project has the required stages
        self._ensure_project_stages()

        # Check if start date is set
        if not self.date_start:
            raise models.ValidationError("La date de début du projet est obligatoire pour générer les tâches.")

        # Check for profile lines if required
        if not self.profile_line_ids and self._project_requires_profiles():
            raise models.ValidationError("Il doit y avoir au moins un profil défini pour générer les tâches.")

        # Check workload validity
        if not self.profiles_workload_valid:
            raise UserError(self.profiles_workload_message)

        # Select the appropriate requirement lines based on project type
        if self.custom_requirements_required:
            requirement_lines = self.custom_requirement_line_ids
        else:
            requirement_lines = self.requirement_line_ids

        # Check if requirements exist
        if not requirement_lines:
            raise models.ValidationError(
                "Aucune exigence n'a été définie. Veuillez ajouter des exigences avant de générer les tâches."
            )

        # Sort requirement lines consistently
        sorted_lines = requirement_lines.sorted(
            key=lambda r: (
                r.order,
                r.planned_end_date or fields.Date.today(),
                r.planned_start_date or fields.Date.today(),
                r.id
            )
        )

        # Create tasks in sequential order
        tasks = []
        sequence = 0

        for req_line in sorted_lines:
            estimated_work_days = req_line.estimated_work_days

            if not estimated_work_days:
                continue

            sequence += 1
            # Create task with the allocated time
            task = self._create_task_for_requirement(
                req_line,
                estimated_work_days,
                is_custom_requirement=self.custom_requirements_required
            )

            if task:
                # Set sequence for sorting in task list view
                task.sudo().write({'sequence': sequence})
                tasks.append(task.id)

        # Update the project state only if tasks were created
        if tasks:
            self.write({
                'stage': 'project',
                'project_created_by': self.env.user.id,
                'project_created_date': fields.Datetime.now()
            })

            # Use the same action as the smart button "Tâches" to get consistent behavior
            action = self.env['ir.actions.act_window'].sudo()._for_xml_id('project.action_view_task')
            action.update({
                'domain': [('id', 'in', tasks)],
                'context': {'default_project_id': self.id}
            })
            return action
        else:
            # No tasks were created, raise an error
            raise models.ValidationError(
                "Aucune tâche n'a été générée. Veuillez vérifier que les exigences du projet ont des jours de travail estimés."
            )

    def _create_task_for_requirement(self, req_line, estimated_work_days, is_custom_requirement=False):
        """
        Create a task for a requirement line or custom requirement line.
        
        Args:
            req_line: The requirement line (regular or custom)
            estimated_work_days: Estimated work days for the task
            is_custom_requirement: Whether the requirement is a custom requirement line (True) or a regular requirement line (False)
        """
        if not req_line or estimated_work_days <= 0:
            return False

        # Validate that we have stages
        if not self.type_ids:
            raise models.ValidationError("Aucune étape de tâche n'est définie pour ce projet.")

        # Get the first stage from project type_ids
        first_stage = self.type_ids[0]

        # Common task values for both types
        task_vals = {
            'project_id': self.id,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'stage_id': first_stage.id,
            'allocated_hours': estimated_work_days * HOURS_PER_DAY,  # Convert days to hours
            'user_ids': [(5, 0, 0)],  # Clear all assigned users
        }

        # Type-specific values
        if is_custom_requirement:
            department_name = req_line.department_id.name if req_line.department_id else ''
            task_vals.update({
                'name': f"{department_name} - {req_line.name}",
                'description': req_line.challenges or '',
                'custom_requirement_line_id': req_line.id,
            })
        else:
            department_name = req_line.department_id.name if req_line.department_id else ''
            task_vals.update({
                'name': f"{department_name} - {req_line.requirement_id.name}",
                'description': req_line.challenges or '',
                'requirement_id': req_line.requirement_id.id,
                'requirement_line_id': req_line.id,
            })

        task = self.env['project.task'].sudo().create(task_vals)

        # Subtask generation code commented out - Can be re-enabled if subtask functionality is needed again
        # Create subtasks for each subrequirement, sorted by sequence
        # sorted_subreqs = req_line.subrequirement_line_ids.sorted(
        #     key=lambda sr: (sr.subrequirement_id.sequence, sr.id)
        # )
        # 
        # # Track subtask sequence
        # subtask_sequence = 0
        # 
        # for subreq_line in sorted_subreqs:
        #     subtask_sequence += 1
        #     subtask_name = f"{department_name} - {subreq_line.subrequirement_id.description}"
        # 
        #     # Use the same start and end dates as the requirement for simplicity
        #     subtask_vals = {
        #         'name': subtask_name,
        #         'parent_id': task.id,
        #         'project_id': self.id,
        #         'partner_id': self.partner_id.id,
        #         'user_ids': [(6, 0, user_ids)],
        #         'planned_date_begin': start_date,
        #         'date_deadline': end_date,
        #         'sequence': subtask_sequence,  # Set sequence for ordering in list view
        #     }
        #     self.env['project.task'].sudo().create(subtask_vals)

        return task

    def _create_task_for_custom_requirement(self, custom_req_line, estimated_work_days):
        """Create a task specifically for a custom requirement"""
        return self._create_task_for_requirement(custom_req_line, estimated_work_days, is_custom_requirement=True)

    def _assign_project_manager_to_tasks(self, task_ids):
        """
        Helper method to assign the project manager to a list of tasks.
        """
        if not task_ids or not self.user_id:
            return False

        # Use direct SQL for better performance
        # First, remove all existing assignees
        self.env.cr.execute("""
            DELETE FROM project_task_user_rel
            WHERE task_id IN %s
        """, (tuple(task_ids),))

        # Then, add only the project manager
        self.env.cr.execute("""
            INSERT INTO project_task_user_rel (task_id, user_id)
            SELECT t.id, %s
            FROM project_task t
            WHERE t.id IN %s
        """, (self.user_id.id, tuple(task_ids)))

        return True

    def _get_department_requirement_lines(self, department):
        """Get requirement lines for a specific department"""
        return self.requirement_line_ids.filtered(
            lambda r: r.requirement_id.department_id == department
        )

    def _calculate_workforce_factor(self):
        """
        Calculate workforce factor from profiles.
        The workforce factor is the sum of all involvement percentages.
        """
        if not self.profile_line_ids:
            return 1.0  # Default to 1.0 if no profiles

        total_involvement = sum(
            profile.involvement_percentage for profile in self.profile_line_ids
            if profile.involvement_percentage
        )

        if total_involvement > 0:
            return total_involvement
        return 1.0  # Default to 1.0 if the sum is 0

    def create_project(self):
        """
        Method called from the project creation form to create a new project
        and redirect to the full project form view
        """
        self.ensure_one()

        # Apply naming conventions based on project type using the helper method
        if self.name:
            self.name = self._format_project_name(
                self.name,
                self.project_type,
                self.from_crm,
                self.from_etude_chiffrage,
                self.implementation_category
            )

        # Return an action to open the created project in the full form view
        return {
            'name': 'Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.id,
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }

    def _format_project_name(self, name, project_type, from_crm=False, from_etude_chiffrage=False,
                             implementation_category=None):
        """
        Format project name according to standardized naming conventions.
        
        Args:
            name: Base project name
            project_type: Type of project ('etude_chiffrage', 'implementation', etc.)
            from_crm: Whether project was created from CRM
            from_etude_chiffrage: Whether project was created from Etude et Chiffrage
            implementation_category: Category for implementation projects ('integration', 'evolution', etc.)
            
        Returns:
            Formatted project name following naming conventions
        """
        if not name:
            return name

        # Remove any existing type-specific suffix to prevent duplication
        clean_name = name
        if " - (E&C)" in clean_name:
            clean_name = clean_name.replace(" - (E&C)", "")
        if " - (Implémentation)" in clean_name:
            clean_name = clean_name.replace(" - (Implémentation)", "")
        if " - (Intégration)" in clean_name:
            clean_name = clean_name.replace(" - (Intégration)", "")
        if " - (Evolution)" in clean_name:
            clean_name = clean_name.replace(" - (Evolution)", "")

        # Add appropriate suffix based on project type
        if project_type == 'etude_chiffrage':
            return f"{clean_name} - (E&C)"
        elif project_type == 'implementation':
            # For implementation projects, use the category name instead of 'Implémentation'
            if implementation_category == 'integration':
                return f"{clean_name} - (Intégration)"
            elif implementation_category == 'evolution':
                return f"{clean_name} - (Evolution)"
            else:
                return f"{clean_name} - (Implémentation)"  # Fallback if no category

        return clean_name

    def _reorder_requirements_after_save(self):
        """
        Trigger requirement reordering after a project save.
        This ensures that order changes made to the project's requirement lines are properly processed.
        """
        for project in self:
            if project.requirement_line_ids:
                # Use the static method to avoid context restrictions
                self.env['project.requirement.line']._reorder_project_requirements(project.id)
        return True

    def write(self, vals):
        """Override write method to add functionality for recomputing complexity."""
        # Track if we need to reorder after save
        requirements_lines_need_reorder = 'requirement_line_ids' in vals

        # Track if departments are being modified
        departments_modified = 'department_ids' in vals

        # Set default name using translation system if name is being cleared or set to empty
        if 'name' in vals and not vals.get('name'):
            vals['name'] = self.env._('Project')

        # Track if we need to clear lot departments after write
        needs_to_clear_lot_departments = False
        # Track if we need to remove generic department after write
        needs_generic_department_removal = False
        # Track if we're changing from evolution to non-evolution
        changing_from_evolution = False

        # Get the generic department outside the conditionals
        generic_department = self._get_generic_department()

        # Handle project type changes
        if 'project_type' in vals:
            # Check if changing from implementation with evolution to another project type
            for record in self:
                # Changing FROM implementation with evolution to another project type
                if record.project_type == 'implementation' and record.implementation_category == 'evolution' and vals[
                    'project_type'] != 'implementation':
                    if generic_department and generic_department in record.department_ids:
                        # Only modify departments if not explicitly set by user
                        if 'department_ids' not in vals:
                            # Remove the generic department
                            new_departments = record.department_ids.filtered(lambda d: d.id != generic_department.id)
                            if not new_departments:  # Ensure we don't end up with empty departments
                                # If this would leave us with no departments, explicitly clear departments
                                vals['department_ids'] = [(5, 0, 0)]
                            else:
                                vals['department_ids'] = [(6, 0, new_departments.ids)]

                        # Flag to remove generic department from lots after super write
                        needs_generic_department_removal = True

            # Ensure implementation fields are cleared when changing to non-implementation project type
            if vals['project_type'] != 'implementation':
                vals['implementation_category'] = False
                vals['department_type'] = False

        # Handle department changes when implementation_category changes to 'evolution'
        if 'implementation_category' in vals and vals['implementation_category'] == 'evolution':
            if generic_department:
                # Set departments to only the generic department
                vals['department_ids'] = [(6, 0, [generic_department.id])]
                # Reset department type to standard
                vals['department_type'] = 'standard'

                # Flag to clear all departments from lots after super write
                needs_to_clear_lot_departments = True

                # Clear all standard requirement lines when switching to evolution project
                for record in self:
                    if record.requirement_line_ids:
                        vals['requirement_line_ids'] = [(5, 0, 0)]  # Clear all standard requirement lines

        # Handle changes from evolution to a different implementation category
        elif 'implementation_category' in vals and vals['implementation_category'] != 'evolution':
            for record in self:
                # Only process if current category is 'evolution'
                if record.implementation_category == 'evolution':
                    changing_from_evolution = True

                    # Only remove generic department if user hasn't explicitly set departments
                    if 'department_ids' not in vals:
                        if generic_department and generic_department in record.department_ids:
                            # Create a new list of departments without the generic department
                            new_departments = record.department_ids.filtered(lambda d: d.id != generic_department.id)

                            # If this would leave us with no departments, we need to handle differently
                            if not new_departments:
                                # Set departments to empty - force user to select departments
                                vals['department_ids'] = [(5, 0, 0)]
                            else:
                                vals['department_ids'] = [(6, 0, new_departments.ids)]

                    # Flag to remove generic department from lots - only if not handled in department_ids
                    needs_generic_department_removal = True

                    # Clear all custom requirement lines when switching from evolution project
                    if record.custom_requirement_line_ids:
                        vals['custom_requirement_line_ids'] = [(5, 0, 0)]  # Clear all custom requirement lines

        # Also check for project_type changes that might affect evolution status
        if 'project_type' in vals:
            for record in self:
                # Check if changing TO implementation with evolution category
                is_becoming_evolution = (vals['project_type'] == 'implementation' and
                                         vals.get('implementation_category') == 'evolution')
                # Check if changing FROM implementation with evolution category
                is_leaving_evolution = (record.project_type == 'implementation' and
                                        record.implementation_category == 'evolution' and
                                        (vals['project_type'] != 'implementation'))

                # Clear standard requirements when becoming an evolution project
                if is_becoming_evolution and record.requirement_line_ids:
                    vals['requirement_line_ids'] = [(5, 0, 0)]

                # Clear custom requirements when leaving an evolution project
                if is_leaving_evolution and record.custom_requirement_line_ids:
                    vals['custom_requirement_line_ids'] = [(5, 0, 0)]

        # Handle name formatting when project type changes
        if 'project_type' in vals:
            for record in self:
                vals['name'] = self._format_project_name(
                    record.name,
                    vals['project_type'],
                    record.from_crm,
                    record.from_etude_chiffrage,
                    vals.get('implementation_category', record.implementation_category)
                )

        # Handle name formatting when implementation category changes for implementation projects
        if 'implementation_category' in vals and vals.get('implementation_category'):
            for record in self:
                if record.project_type == 'implementation' or vals.get('project_type') == 'implementation':
                    # Get the project type (either current or changed)
                    project_type = vals.get('project_type', record.project_type)
                    vals['name'] = self._format_project_name(
                        record.name,
                        project_type,
                        record.from_crm,
                        record.from_etude_chiffrage,
                        vals['implementation_category']
                    )

        # Add a context flag to prevent reordering during project save
        context = self.env.context.copy()
        if not context.get('skip_reordering'):
            context['skip_reordering'] = True

        # Execute standard write method with the updated context
        res = super(Project, self.with_context(context)).write(vals)

        # Clear ALL departments from lots if changing to evolution
        if needs_to_clear_lot_departments:
            for project in self:
                if project.lot_ids:
                    # Clear all departments from all lots
                    for lot in project.lot_ids:
                        lot.with_context(skip_department_validation=True).write({
                            'department_ids': [(5, 0, 0)]  # Clear all departments
                        })

        # Remove generic department from lots if changing from evolution
        if needs_generic_department_removal and changing_from_evolution:
            for project in self:
                if project.lot_ids and generic_department:
                    for lot in project.lot_ids:
                        # Only remove generic department if it exists in the lot
                        if generic_department in lot.department_ids:
                            # Get lot departments excluding generic department
                            new_lot_departments = lot.department_ids.filtered(lambda d: d.id != generic_department.id)
                            # Update lot departments
                            lot.with_context(skip_department_validation=True).write({
                                'department_ids': [(6, 0, new_lot_departments.ids)]
                            })

        # Recompute complexity for all subrequirement lines
        self._recompute_subrequirements_complexity()

        # If requirements were modified, trigger reordering after save
        if requirements_lines_need_reorder:
            self._reorder_requirements_after_save()

        # If departments were modified, remove requirement lines for removed departments
        if departments_modified:
            self._remove_requirement_lines_for_removed_departments()

        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Override create method to add functionality for recomputing complexity."""
        # Apply naming conventions based on project type
        for vals in vals_list:
            # Set default name using translation system if name is empty
            if not vals.get('name'):
                vals['name'] = self.env._('Project')

            # Always apply type-based formatting for the name
            if vals.get('name') and vals.get('project_type'):
                vals['name'] = self._format_project_name(
                    vals['name'],
                    vals['project_type'],
                    vals.get('from_crm', False),
                    vals.get('from_etude_chiffrage', False),
                    vals.get('implementation_category', False)
                )

        # Execute standard create method
        projects = super().create(vals_list)
        # Handle CRM lead linking if project was created from CRM
        for project in projects:
            # Apply default task types if not already set
            if not project.type_ids:
                project._apply_default_task_types()

            # Link project to CRM lead if created from CRM
            if self.env.context.get('crm_lead_id'):
                crm_lead = self.env['crm.lead'].browse(self.env.context['crm_lead_id'])
                if crm_lead.exists():
                    crm_lead.write({'project_id': project.id})

        # Recompute complexity for all subrequirement lines
        projects._recompute_subrequirements_complexity()

        return projects

    def _remove_requirement_lines_for_removed_departments(self):
        """
        Remove requirement lines associated with departments that are no longer in the project.
        This keeps the requirements list clean when departments are removed.
        """
        for project in self:
            # Get current department IDs
            department_ids = project.department_ids.ids

            # Remove standard requirement lines for departments no longer in the project
            to_remove = project.requirement_line_ids.filtered(
                lambda r: r.requirement_id.department_id.id not in department_ids
            )
            if to_remove:
                to_remove.with_context(
                    skip_auto_subrequirements=True,
                    from_requirements_insertion=True
                ).unlink()

            # Remove custom requirement lines for departments no longer in the project
            custom_to_remove = project.custom_requirement_line_ids.filtered(
                lambda r: r.department_id.id not in department_ids
            )
            if custom_to_remove:
                custom_to_remove.unlink()

    def _project_requires_profiles(self):
        """
        Core business logic: determine if this project type uses profiles.
        This drives both UI visibility and validation requirements.
        """
        self.ensure_one()

        # etude_chiffrage projects don't use profiles
        if self.project_type == 'etude_chiffrage':
            return False

        # Default to required
        return True

    def _project_shows_requirements_tab(self):
        """
        Core business logic: determine if this project type should show the requirements tab.
        This only controls UI visibility.
        """
        self.ensure_one()

        # Default to visible
        return True

    def _project_requires_requirements(self):
        """
        Core business logic: determine if this project type requires requirements.
        This drives validation requirements only.
        """
        self.ensure_one()

        # etude_chiffrage projects can use requirements but they're optional
        if self.project_type == 'etude_chiffrage':
            return False

        # Default to required
        return True
