import base64
import io

import xlsxwriter
from PIL import Image

from odoo import models, fields, api, _
from .common import PROJECT_STATUS_SELECTION, STANDARD_DEPARTMENT_NAME
from ...project_requirement.models.common_dates import (
    get_monday_of_week
)

# Status mapping between custom status and native status
STATUS_MAPPING = {
    'sunny': 'on_track',
    'cloudy': 'at_risk',
    'rainy': 'off_track',
    'on_track': 'sunny',
    'at_risk': 'cloudy',
    'off_track': 'rainy',
}

# Custom status color mapping
CUSTOM_STATUS_COLOR = {
    'sunny': 20,  # Green
    'cloudy': 22,  # Orange
    'rainy': 23,  # Red
    False: 0,  # Default grey
}

# State selection options for project updates
UPDATE_STATE_SELECTION = [
    ('draft', 'Brouillon'),
    ('sent', 'Envoyé')
]


class ProjectUpdate(models.Model):
    _inherit = 'project.update'

    name = fields.Char(string='Rapport', store=True, readonly=False, required=True)
    custom_status = fields.Selection(PROJECT_STATUS_SELECTION, string='Statut', default='sunny', required=True)
    custom_status_color = fields.Integer(string='Couleur statut', compute='_compute_custom_status_color')
    department_type = fields.Selection(related='project_id.department_type', string='Suivi département',
                                       readonly=True, store=False)
    department_ids = fields.Many2many(related='project_id.department_ids', string='Départements', readonly=True)
    project_flash_report_line_ids = fields.One2many('project.flash.report.line', 'project_update_id',
                                                    string='Lignes de Flash Report')
    project_tracking_report_line_ids = fields.One2many('project.tracking.report.line', 'project_update_id',
                                                       string='Lignes de Suivi Projet')
    state = fields.Selection(UPDATE_STATE_SELECTION, string='État', default='draft', tracking=True, copy=False)

    # Use report_date as the main date field
    report_date = fields.Datetime(string='Date de début du rapport', required=True)
    report_date_end = fields.Datetime(string='Date de fin du rapport')

    def _get_update_name(self, report_date=None, report_date_end=None):
        """Helper method to generate update name based on report date."""
        if not report_date:
            return "Nouveau rapport"

        # Get the date part ("DD/MM/YYYY")
        if isinstance(report_date, str):
            report_date = fields.Datetime.from_string(report_date)
        date = fields.Date.from_string(report_date)
        formatted_date = date.strftime('%d/%m/%Y')

        # If we have an end date, include it in the name
        if report_date_end:
            if isinstance(report_date_end, str):
                report_date_end = fields.Datetime.from_string(report_date_end)
            end_date = fields.Date.from_string(report_date_end)
            formatted_end_date = end_date.strftime('%d/%m/%Y')
            return f"Période du {formatted_date} au {formatted_end_date}"
        else:
            return f"Période du {formatted_date}"

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        # Get the active project from context
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')

        if active_model == 'project.project' and active_id:
            # Get the project
            project = self.env['project.project'].browse(active_id)
            result['project_id'] = project.id

        # Always set our default values, overriding parent's behavior
        result['description'] = ''
        result['custom_status'] = 'sunny'
        result['status'] = 'on_track'

        # Set default report date to Monday of current week
        today = fields.Date.context_today(self)
        monday = get_monday_of_week(today)
        result['report_date_end'] = False
        result['report_date'] = fields.Datetime.from_string(monday)
        result['date'] = monday  # Set native date to Monday as well
        result['name'] = self._get_update_name(result['report_date'])

        return result

    @api.model_create_multi
    def create(self, vals_list):
        # Process each record being created
        for vals in vals_list:
            # Always set a name before creation to avoid validation errors
            if not vals.get('name'):
                # Generate name based on report date if available
                vals['name'] = self._get_update_name(
                    report_date=vals.get('report_date'),
                    report_date_end=vals.get('report_date_end')
                )

            # Set default status if not provided
            if 'custom_status' not in vals:
                vals['custom_status'] = 'sunny'
            if 'status' not in vals:
                vals['status'] = 'on_track'

            # Ensure report_date is set to the native date field
            if 'report_date' in vals and 'date' not in vals:
                vals['date'] = fields.Date.from_string(vals['report_date'])
            # If date is set but report_date is not, sync report_date with date
            elif 'date' in vals and 'report_date' not in vals:
                vals['report_date'] = fields.Datetime.from_string(vals['date'])

        # Create the records
        updates = super().create(vals_list)

        # For each update, check if it's the first one and generate report lines if needed
        # Skip line generation if called from the wizard (wizard handles its own logic)
        for update in updates:
            if not self.env.context.get('wizard_creating_update'):
                project = update.project_id

                # Find the immediately preceding update for this project
                previous_updates = self.search([
                    ('project_id', '=', project.id),
                    ('id', '!=', update.id)
                ], order='report_date desc, id desc', limit=1)

                # Generate lines based on whether it's the first update or not
                update.generate_flash_lines(last_update=previous_updates)
                update.generate_tracking_lines(last_update=previous_updates)

        return updates

    def write(self, vals):
        """Override write to ensure name stays consistent with report date."""

        # Sync report_date to native date field if one is changing
        if 'report_date' in vals and 'date' not in vals:
            vals['date'] = fields.Date.from_string(vals['report_date'])
        elif 'date' in vals and 'report_date' not in vals:
            date_to_sync = vals['date'] if vals.get('date') else self.date
            if date_to_sync:
                vals['report_date'] = fields.Datetime.from_string(date_to_sync)

        # Handle name update only if the report date is changing
        if 'report_date' in vals or 'report_date_end' in vals:
            for record in self:
                # Determine the final date values after the write
                final_start_date = vals.get('report_date', record.report_date)
                final_end_date = vals.get('report_date_end', record.report_date_end)
                update_vals_end_date = False  # Flag to track if vals['report_date_end'] needs update

                # Apply date logic if we have a start date
                if final_start_date:
                    # Ensure end date is logical and clear if same day as start
                    if final_end_date:
                        start_dt = fields.Datetime.from_string(final_start_date) if isinstance(final_start_date,
                                                                                               str) else final_start_date
                        end_dt = fields.Datetime.from_string(final_end_date) if isinstance(final_end_date,
                                                                                           str) else final_end_date

                        if start_dt and end_dt:  # Ensure both are valid datetime
                            # 1. Adjust end date if it's before start date
                            if end_dt < start_dt:
                                final_end_date = final_start_date
                                update_vals_end_date = True

                            # Use the potentially corrected end date for same-day check
                            corrected_end_dt = fields.Datetime.from_string(final_end_date) if isinstance(final_end_date,
                                                                                                         str) else final_end_date

                            # 2. Clear end date if it's the same day as start date
                            start_date_obj = fields.Date.from_string(start_dt)
                            end_date_obj = fields.Date.from_string(corrected_end_dt)
                            if start_date_obj == end_date_obj:
                                final_end_date = False
                                update_vals_end_date = True
                    # else: final_end_date remains as it was (could be False already)

                # Update vals['report_date_end'] if it was corrected or cleared
                if update_vals_end_date:
                    vals['report_date_end'] = final_end_date

                # Update name based on the final adjusted dates
                vals['name'] = record._get_update_name(final_start_date, final_end_date)

        return super().write(vals)

    def copy(self, default=None):
        """Override copy to ensure proper handling of dates and data."""
        default = default or {}

        # Don't copy the state - new copies are always drafts
        default['state'] = 'draft'

        # Always reset status to sunny for copied updates
        default['custom_status'] = 'sunny'
        default['status'] = 'on_track'

        # Create the copy
        new_record = super().copy(default)

        # For flash report lines
        for line in self.project_flash_report_line_ids:
            # Copy the line but reset all HTML fields
            new_line = line.copy({
                'project_update_id': new_record.id,
                # Copy HTML fields from the original line
                'tasks_completed': line.tasks_completed,
                'tasks_in_progress': line.tasks_in_progress,
                'upcoming_deliveries': line.upcoming_deliveries,
                'attention_points': line.attention_points
            })

        # For tracking report lines, copy to new record
        for line in self.project_tracking_report_line_ids:
            line.copy({
                'project_update_id': new_record.id
            })

        return new_record

    @api.depends('custom_status')
    def _compute_custom_status_color(self):
        """Compute the custom_status_color based on the custom_status"""
        for update in self:
            update.custom_status_color = CUSTOM_STATUS_COLOR[update.custom_status]

    @api.onchange('report_date', 'report_date_end')
    def _onchange_report_date(self):
        """Adjust dates, sync native date, and update name on date changes."""
        warning = None
        start_date = self.report_date
        end_date = self.report_date_end

        # Ensure dates are logical
        if start_date and end_date:
            start_dt = fields.Datetime.from_string(start_date)
            end_dt = fields.Datetime.from_string(end_date)

            # 1. Check if end date is before start date
            if end_dt < start_dt:
                self.report_date_end = False  # Clear the end date
                end_date = False  # Update local variable for subsequent logic
                # Prepare warning message
                warning = {
                    'title': _("Date invalide"),
                    'message': _("La date de fin ne peut pas être antérieure à la date de début."),
                }
            else:
                # 2. Clear end date if it's the same day as start date
                # (Check only if end date was not already cleared above)
                start_date_obj = fields.Date.from_string(start_dt)
                end_date_obj = fields.Date.from_string(end_dt)
                if start_date_obj == end_date_obj:
                    self.report_date_end = False
                    end_date = False  # Update local variable for name generation

        # Sync native date field with the start date
        if start_date:
            native_date = fields.Date.from_string(start_date)
            if self.date != native_date:
                self.date = native_date
        elif self.date:  # Clear native date if start date is removed
            self.date = False

        # Update the name using the potentially modified dates
        self.name = self._get_update_name(self.report_date, self.report_date_end)

        if warning:
            return {'warning': warning}

    @api.onchange('custom_status')
    def _onchange_custom_status(self):
        """Map custom status to native status when it changes"""
        for update in self:
            if update.custom_status:
                update.status = STATUS_MAPPING.get(update.custom_status, 'on_track')

    @api.onchange('status')
    def _onchange_status(self):
        """Map native status to custom status when it changes"""
        for update in self:
            if update.status:
                update.custom_status = STATUS_MAPPING.get(update.status, 'sunny')

    @api.model
    def message_post_with_template(self, template_id, res_id=None, **kwargs):
        """Override to mark the report as sent after sending email."""
        result = super().message_post_with_template(template_id, res_id, **kwargs)

        # Check if we need to mark the update as sent
        if self._context.get('mark_update_as_sent'):
            self.browse(res_id).write({'state': 'sent'})

        return result

    def action_send_by_email(self):
        """Send the report by email, attach generated reports, and mark it as sent."""
        self.ensure_one()

        # Generate reports and get attachment IDs
        attachment_ids = []
        flash_attachment = self._generate_flash_report_attachment()
        if flash_attachment:
            attachment_ids.append(flash_attachment.id)
        tracking_attachment = self._generate_tracking_report_attachment()
        if tracking_attachment:
            attachment_ids.append(tracking_attachment.id)

        # Open the email compose wizard with attachments
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': 'project.update',
                'default_res_ids': [self.id],
                'default_use_template': True,
                'default_template_id': self.env.ref('project_reporting.mail_template_project_update').id,
                'default_composition_mode': 'comment',
                'force_email': True,
                'mark_update_as_sent': True,
                'default_mark_update_as_sent': True,
                'default_attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else [],  # Pass attachment IDs
            },
        }

    def action_set_to_draft(self):
        """Reset the update to draft state."""
        self.ensure_one()
        return self.write({'state': 'draft'})

    def action_add_end_date(self):
        """Add an end date to the report."""
        self.ensure_one()
        # Set the end date to the same as the start date
        self.report_date_end = self.report_date

        return True

    def create_new_update_wizard(self):
        """Open the create update wizard."""
        return {
            'name': _('Créer une mise à jour de projet'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': self._context,
        }

    def group_tracking_lines_by_lot(self):
        """Groupe les lignes de suivi par lot puis par département"""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'project.tracking.report.line',
            'name': 'Lignes de Suivi par Lot et Département',
            'view_mode': 'list,form',
            'domain': [('project_update_id', '=', self.id)],
            'context': {
                'group_by': ['lot_number', 'department'],
                'create': False,
            },
            'target': 'current',
        }
        return action

    def _generate_flash_report_attachment(self):
        """Generate PDF report for the flash report part and return the attachment."""
        self.ensure_one()
        try:
            # Get the report action reference
            report_action = self.env.ref("project_reporting.action_report_project_update_flash_report")

            # Generate the PDF content
            # Explicitly use res_ids keyword argument to avoid ambiguity
            report_ref = 'project_reporting.action_report_project_update_flash_report'
            pdf_content, content_type = report_action._render_qweb_pdf(report_ref, res_ids=[self.id])

            # Create the attachment
            filename = f"Flash Report - {self.name.replace('/', '-')}.pdf"
            attachment = self.env["ir.attachment"].create(
                {
                    "name": filename,
                    "datas": base64.b64encode(pdf_content),
                    "res_model": self._name,
                    "res_id": self.id,
                    "type": "binary",
                    "mimetype": "application/pdf",
                }
            )
            return attachment
        except Exception as e:
            # Re-raise the exception so it's not swallowed silently
            raise

    def generate_flash_report_pdf(self):
        """Generate PDF report for the flash report part and return download action."""
        self.ensure_one()
        attachment = self._generate_flash_report_attachment()
        if attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        # Handle error case - maybe return a notification?
        return {'type': 'ir.actions.act_window_close'}

    def _generate_tracking_report_attachment(self):
        """Generate Excel report for the tracking report part and return the attachment."""
        self.ensure_one()
        try:
            # Define all colors as variables
            # Main colors
            PRIMARY_BLUE = '#0b5394'  # Main blue color for headers, requirements, data bars
            WHITE = '#ffffff'  # White for backgrounds and text
            # Professional progress bar colors with good contrast for text
            LIGHT_BLUE = '#b3c6e7'  # Light blue for progress bars
            SUCCESS_GREEN = '#6aa84f'  # Green for 100% complete values

            # Create a buffer for the Excel file
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {
                'in_memory': True,
                'default_format_properties': {
                    'font_name': 'Roboto',
                    'valign': 'vcenter'  # Set vertical alignment to center by default
                }
            })

            # Define workbook formats
            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 20,
                'bg_color': PRIMARY_BLUE,
                'font_color': WHITE
            })

            # Header format for the first two columns - white background with blue text
            table_header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': WHITE,
                'border': 1,
                'text_wrap': True,
                'font_color': PRIMARY_BLUE,
                'font_size': 13
            })

            logo_format = workbook.add_format({
                'bg_color': WHITE,
                'border': 1,
                'border_color': 'black'
            })

            # Header format for columns from Sous-Exigences to Commentaires - blue background with white text
            table_header_blue_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': PRIMARY_BLUE,
                'border': 1,
                'text_wrap': True,
                'font_color': WHITE,
                'font_size': 13
            })

            # Department cells with white background and blue text (bold)
            dept_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'border': 1,
                'bg_color': WHITE,
                'font_color': PRIMARY_BLUE,
                'border_color': 'black',
                'font_size': 13
            })

            # Group tracking report lines by lot and then by department
            lot_department_lines = {}

            # First, gather all lot numbers and sort them
            lots = set()
            for line in self.project_tracking_report_line_ids:
                lot = line.lot_number or "Lot ?"
                lots.add(lot)

            # Sort lots (alphabetically/numerically)
            sorted_lots = sorted(list(lots))

            # Group by lot then by department
            for line in self.project_tracking_report_line_ids:
                lot = line.lot_number or "Lot ?"
                if lot not in lot_department_lines:
                    lot_department_lines[lot] = {}

                department = line.department
                if department not in lot_department_lines[lot]:
                    lot_department_lines[lot][department] = []

                lot_department_lines[lot][department].append(line)

            # Create common function to setup worksheet properties
            def setup_worksheet(worksheet, title):
                worksheet.set_column('A:A', 40)  # Département
                worksheet.set_column('B:B', 20)  # Exigences
                worksheet.set_column('C:C', 60)  # Sous-exigences
                worksheet.set_column('D:D', 18)  # % Conception & Dev.
                worksheet.set_column('E:E', 18)  # % Validation
                worksheet.set_column('F:F', 18)  # % Integration
                worksheet.set_column('G:G', 18)  # Date Livraison Prévue
                worksheet.set_column('H:H', 18)  # Date Livraison Réelle
                worksheet.set_column('I:I', 60)  # Commentaires

                # Set row heights
                worksheet.set_row(0, 16)  # Title row
                worksheet.set_row(1, 16)  # Title row
                worksheet.set_row(2, 16)  # Title row
                worksheet.set_row(3, 20)  # Empty space row

                # Create empty merged cells for logos
                # Left logo area
                worksheet.merge_range('A1:A3', '', logo_format)

                # Title spans rows 1-3, from column B to column I
                worksheet.merge_range('B1:H3', title, header_format)

                # Right logo area
                worksheet.merge_range('I1:I3', '', logo_format)

                # Add logos to the worksheet
                # Get the client's company logo (from project's partner)
                client_logo = None
                if self.project_id.partner_id:
                    partner = self.project_id.partner_id
                    # If partner is a person (not a company), try to get their parent company's logo
                    if not partner.is_company and partner.parent_id and partner.parent_id.image_1920:
                        client_logo = partner.parent_id.image_1920
                    # Otherwise use the partner's logo directly if it's a company
                    elif partner.is_company and partner.image_1920:
                        client_logo = partner.image_1920

                # Get the current company logo
                company_logo = self.env.company.logo
                
                def get_image_data_and_scale(image_b64, cell_width, cell_height):
                    """
                    Decode a base64 image, return a BytesIO buffer and the scale to fit in the cell.
                    Args:
                        image_b64 (str): Base64-encoded image.
                        cell_width (int): Target cell width in px.
                        cell_height (int): Target cell height in px.
                    Returns:
                        (BytesIO, float): image_data buffer, scale factor
                    """
                    image_data = io.BytesIO(base64.b64decode(image_b64))
                    image_data.seek(0)
                    with Image.open(image_data) as img:
                        img_width, img_height = img.size
                    x_scale = min(1.0, cell_width / img_width)
                    y_scale = min(1.0, cell_height / img_height)
                    scale = min(x_scale, y_scale)
                    image_data.seek(0)
                    return image_data, scale
                
                # Insert client logo in left cell if available
                if client_logo:
                    image_data, scale = get_image_data_and_scale(client_logo, 400, 50)
                    worksheet.insert_image('A1', 'client_logo.png',
                                           {'image_data': image_data,
                                            'x_scale': scale, 'y_scale': scale,
                                            'x_offset': 2, 'y_offset': 2,
                                            'object_position': 1})  # Centrer l'image dans la cellule

                # Insert company logo in right cell
                if company_logo:
                    image_data, scale = get_image_data_and_scale(company_logo, 400, 50)
                    worksheet.insert_image('I1', 'company_logo.png',
                                           {'image_data': image_data,
                                            'x_scale': scale, 'y_scale': scale,
                                            'x_offset': 2, 'y_offset': 2,
                                            'object_position': 1})  # Center the image in the cell

                # Empty separator line
                worksheet.merge_range('A4:I4', '')

                # Table headers
                row = 4  # 0-indexed, so row 5 in Excel
                worksheet.set_row(row, 45)
                headers = [
                    'Département', 'Exigences', 'Sous-Exigences',
                    '% Conception & Dev.', '% Validation', '% Integration',
                    'Date Livraison Prévue', 'Date Livraison Réelle', 'Commentaires'
                ]
                for col, header in enumerate(headers):
                    # Use different formats for different columns
                    if col < 2:  # Département and Exigences - white bg with blue text
                        worksheet.write(row, col, header, table_header_format)
                    else:  # Sous-Exigences to Commentaires - blue bg with white text
                        worksheet.write(row, col, header, table_header_blue_format)

                return 5  # Return starting row for data

            # Function to write department data
            def write_department_data(worksheet, department_name, lines, start_row, add_separator=False):
                row = start_row

                # Group lines by requirement
                requirement_groups = {}
                for line in lines:
                    if line.requirement not in requirement_groups:
                        requirement_groups[line.requirement] = []
                    requirement_groups[line.requirement].append(line)

                # Department start row
                department_start_row = row

                # Track total rows for this department
                total_dept_rows = sum(len(req_group) for req_group in requirement_groups.values())

                # Try to find department object to get short name
                dept_obj = None
                for dept in self.department_ids:
                    if dept.name == department_name:
                        dept_obj = dept
                        break

                # Use short name for display if available
                display_dept_name = dept_obj.short_name if dept_obj and dept_obj.short_name else department_name

                # Process each requirement group to build table data
                req_group_count = 0
                for requirement, req_lines in requirement_groups.items():
                    # Skip requirements with no subrequirements
                    if not req_lines:
                        continue

                    req_start_row = row
                    req_group_count += 1

                    for i, line in enumerate(req_lines):
                        # Set row height for all data rows
                        worksheet.set_row(row, 23)

                        # Only write department name in the first row of the department
                        if i == 0 and req_start_row == department_start_row:
                            # Merge department column for all rows in this department
                            if total_dept_rows > 0:  # Check before merging
                                worksheet.merge_range(department_start_row, 0,
                                                      department_start_row + total_dept_rows - 1, 0,
                                                      display_dept_name, dept_format)

                        # Only write requirement in the first row of each requirement group
                        if i == 0:
                            # Requirement format with thick borders to match the group border style
                            req_thick_format = workbook.add_format({
                                'bold': True,
                                'align': 'center',
                                'valign': 'vcenter',
                                'text_wrap': True,
                                'border': 1,  # Regular border as base
                                'bg_color': PRIMARY_BLUE,
                                'font_color': WHITE,
                                'border_color': 'black',
                                'font_size': 13
                            })

                            # Set thick borders
                            req_thick_format.set_left(2)
                            req_thick_format.set_right(2)
                            req_thick_format.set_top(2)

                            # For single-row requirements, add bottom border
                            if len(req_lines) == 1:
                                req_thick_format.set_bottom(2)
                                worksheet.write(req_start_row, 1, requirement, req_thick_format)
                            else:
                                # For multi-row requirements
                                # First apply the merge with the top format
                                worksheet.merge_range(req_start_row, 1, req_start_row + len(req_lines) - 1, 1,
                                                      requirement, req_thick_format)

                                # Then create the bottom format with all the same properties plus thick bottom
                                bottom_req_format = workbook.add_format({
                                    'bold': True,
                                    'align': 'center',
                                    'valign': 'vcenter',
                                    'text_wrap': True,
                                    'border': 1,
                                    'bg_color': PRIMARY_BLUE,
                                    'font_color': WHITE,
                                    'border_color': 'black',
                                    'font_size': 13,
                                    'bottom': 2,
                                    'left': 2,
                                    'right': 2
                                })

                                # Apply the bottom format (this won't affect the displayed text from the merge)
                                worksheet.write(req_start_row + len(req_lines) - 1, 1, '', bottom_req_format)

                        # Determine border properties based on position
                        is_first_row = (i == 0)
                        is_last_row = (i == len(req_lines) - 1)

                        # Dynamically create formats with appropriate borders based on position
                        # Create new format objects with the same properties as the base formats

                        # For the first column (subrequirement)
                        subrequirement_format = workbook.add_format({
                            'border': 1,
                            'border_color': 'black',
                            'font_color': PRIMARY_BLUE
                        })
                        if is_first_row:
                            subrequirement_format.set_top(2)  # Thick top border for first row
                        if is_last_row:
                            subrequirement_format.set_bottom(2)  # Thick bottom border for last row
                        subrequirement_format.set_left(2)  # Always thick left border as this is leftmost column

                        # For percentage columns (columns 3-5)
                        percentage_cell_format = workbook.add_format({
                            'border': 1,
                            'border_color': 'black',
                            'num_format': '0%',
                            'font_color': PRIMARY_BLUE,
                            'font_size': 10,
                            'align': 'center'
                        })
                        if is_first_row:
                            percentage_cell_format.set_top(2)  # Thick top border for first row
                        if is_last_row:
                            percentage_cell_format.set_bottom(2)  # Thick bottom border for last row

                        # For date columns (columns 6-7)
                        date_cell_format = workbook.add_format({
                            'border': 1,
                            'border_color': 'black',
                            'num_format': 'dd/mm/yyyy',
                            'font_color': PRIMARY_BLUE,
                            'font_size': 10,
                            'align': 'center'
                        })
                        if is_first_row:
                            date_cell_format.set_top(2)  # Thick top border for first row
                        if is_last_row:
                            date_cell_format.set_bottom(2)  # Thick bottom border for last row

                        # For the last column (comments)
                        comment_format = workbook.add_format({
                            'border': 1,
                            'border_color': 'black',
                            'font_color': PRIMARY_BLUE
                        })
                        if is_first_row:
                            comment_format.set_top(2)  # Thick top border for first row
                        if is_last_row:
                            comment_format.set_bottom(2)  # Thick bottom border for last row
                        comment_format.set_right(2)  # Always thick right border as this is rightmost column

                        # Write cells with dynamically created formats
                        worksheet.write(row, 2, line.subrequirement or "", subrequirement_format)
                        worksheet.write(row, 3, line.design_implementation_percentage / 100, percentage_cell_format)
                        worksheet.write(row, 4, line.validation_percentage / 100, percentage_cell_format)
                        worksheet.write(row, 5, line.integration_percentage / 100, percentage_cell_format)

                        # Date cells
                        worksheet.write(row, 6, line.delivery_planned_date or "", date_cell_format)
                        worksheet.write(row, 7, line.delivery_actual_date or "", date_cell_format)

                        # Comments
                        worksheet.write(row, 8, line.comments or "", comment_format)

                        row += 1

                # Create a sanitized table name from department name (remove spaces, special chars)
                # Try to find department object to get short name
                dept_obj = None
                for dept in self.department_ids:
                    if dept.name == department_name:
                        dept_obj = dept
                        break

                # Use short name for table name if available
                name_for_table = dept_obj.short_name if dept_obj and dept_obj.short_name else department_name
                table_name = "Table" + ''.join(c for c in name_for_table if c.isalnum())

                # Add table with named style
                worksheet.add_table(f'C{start_row + 1}:I{start_row + total_dept_rows}', {
                    'header_row': False,
                    'name': table_name,  # Name the table after the department
                    'style': 'Table Style Light 9',  # Use a style with alternating row colors
                    'columns': [
                        {'header': 'Sous-Exigences'},
                        {'header': '% Conception & Dev.'},
                        {'header': '% Validation'},
                        {'header': '% Integration'},
                        {'header': 'Date Livraison Prévue'},
                        {'header': 'Date Livraison Réelle'},
                        {'header': 'Commentaires'}
                    ]
                })

                return row  # Return the next available row

            # Function to add conditional formatting
            def add_conditional_formatting(worksheet, first_data_row, last_data_row):
                # Ensure last_data_row >= first_data_row before applying formatting
                if last_data_row < first_data_row:
                    return

                # Add data bars to percentage columns
                for col_letter in ['D', 'E', 'F']:
                    worksheet.conditional_format(f'{col_letter}{first_data_row}:{col_letter}{last_data_row}', {
                        'type': 'data_bar',
                        'bar_color': LIGHT_BLUE,  # Light blue for progress bars
                        'bar_only': False,
                        'bar_solid': True,
                        'min_type': 'num',
                        'min_value': 0,
                        'max_type': 'num',
                        'max_value': 1
                    })

                    # Special formatting for 100% values
                    complete_format = workbook.add_format({
                        'bold': True,
                        'font_color': PRIMARY_BLUE,
                        'num_format': '0%',
                        'align': 'center'
                    })

                    worksheet.conditional_format(f'{col_letter}{first_data_row}:{col_letter}{last_data_row}', {
                        'type': 'cell',
                        'criteria': '=',
                        'value': 1,
                        'format': complete_format
                    })

            # Create worksheets based on lot and department order
            # Process lots in sorted order
            for lot in sorted_lots:
                # For each lot, create a sheet for each department
                for department_name, lines in lot_department_lines[lot].items():
                    # Get department short name if available
                    department_obj = None
                    for dept in self.department_ids:
                        if dept.name == department_name:
                            department_obj = dept
                            break

                    # Use short name if available, otherwise use full name for sheet name
                    sheet_name = department_obj.short_name if department_obj and department_obj.short_name else department_name

                    # Truncate sheet name to 31 characters (Excel limitation)
                    sheet_name = sheet_name[:31]

                    # Create sheet and setup
                    worksheet = workbook.add_worksheet(sheet_name)

                    # Use short name in title if available
                    display_name = department_obj.short_name if department_obj and department_obj.short_name else department_name

                    # Handle "Lot ?" differently in the title
                    if lot == "Lot ?":
                        title = f"SUIVI DU DEPARTEMENT {display_name.upper()} - LOT ?"
                    else:
                        title = f"SUIVI DU DEPARTEMENT {display_name.upper()} - {lot.upper()}"

                    start_row = setup_worksheet(worksheet, title)  # start_row is 1-based Excel row

                    # Write data
                    last_row = write_department_data(worksheet, department_name, lines,
                                                     start_row)  # last_row is the next available 1-based Excel row

                    # Add conditional formatting - make sure to include the last actual data row
                    if last_row > start_row:
                        add_conditional_formatting(worksheet, start_row + 1, last_row)

            # Close workbook and get the file data
            workbook.close()
            output.seek(0)

            # Create the attachment
            # Replace slashes with hyphens in the name specifically for the filename
            filename_safe_name = self.name.replace('/', '-')
            filename = f"Suivi Projet - {filename_safe_name}.xlsx"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'datas': base64.b64encode(output.getvalue()),
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })

            return attachment
        except Exception as e:
            # Re-raise the exception so it's not swallowed silently
            raise

    def generate_tracking_report_excel(self):
        """Generate Excel report for the tracking report part and return download action."""
        self.ensure_one()
        attachment = self._generate_tracking_report_attachment()
        if attachment:
            # Return action to download the report
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        # Handle error case - maybe return a notification?
        return {'type': 'ir.actions.act_window_close'}

    def generate_flash_lines(self, last_update=None):
        """
        Generates flash report lines for this update based on current project departments.
        If project department_type is 'standard', creates one line "Tout département confondu".
        If project department_type is 'custom', creates one line per department.
        Copies fields in last_update.
        Existing flash report lines for this update will be deleted.
        """
        self.ensure_one()
        project = self.project_id
        FlashLine = self.env['project.flash.report.line']
        standard_dept_name = STANDARD_DEPARTMENT_NAME

        # Remove existing lines first
        self.project_flash_report_line_ids.unlink()

        lines_to_create = []
        last_lines_by_dept = {}
        if last_update and last_update.project_flash_report_line_ids:
            # Prepare lookup for last update lines by department name
            last_lines_by_dept = {
                line.department: line
                for line in last_update.project_flash_report_line_ids
            }

        if self.department_type == 'standard':
            # Standard: Create one line for all departments
            line_vals = {
                'project_update_id': self.id,
                'department': standard_dept_name,
                'project_status': 'sunny',  # Default status
                'tasks_completed': '',
                'tasks_in_progress': '',
                'upcoming_deliveries': '',
                'attention_points': '',
            }

            # Copy HTML fields only if last update was also standard and had the summary line
            if last_update and last_update.department_type == 'standard':
                last_line = last_lines_by_dept.get(standard_dept_name)
                if last_line:
                    line_vals.update({
                        'tasks_completed': last_line.tasks_completed,
                        'tasks_in_progress': last_line.tasks_in_progress,
                        'upcoming_deliveries': last_line.upcoming_deliveries,
                        'attention_points': last_line.attention_points,
                    })

            lines_to_create.append(line_vals)

        else:  # Custom: Create one line per department
            for department in project.department_ids:
                # Initialize new line values with defaults
                line_vals = {
                    'project_update_id': self.id,
                    'department': department.name,
                    'project_status': 'sunny',  # Default status
                    'tasks_completed': '',
                    'tasks_in_progress': '',
                    'upcoming_deliveries': '',
                    'attention_points': '',
                }

                # Copy fields from the matching department line in the last update, if it exists.
                last_line = last_lines_by_dept.get(department.name)
                if last_line:
                    line_vals.update({
                        'tasks_completed': last_line.tasks_completed,
                        'tasks_in_progress': last_line.tasks_in_progress,
                        'upcoming_deliveries': last_line.upcoming_deliveries,
                        'attention_points': last_line.attention_points,
                    })

                lines_to_create.append(line_vals)

        if lines_to_create:
            FlashLine.create(lines_to_create)

    def generate_tracking_lines(self, last_update=None):
        """
        Generates tracking report lines for this update.
        If last_update is provided, it copies data from its lines.
        Otherwise, it creates new lines based on project requirements.
        Existing tracking report lines for this update will be deleted.
        """
        self.ensure_one()
        project = self.project_id
        TrackingLine = self.env['project.tracking.report.line']

        # Remove existing lines first
        self.project_tracking_report_line_ids.unlink()

        lines_to_create = []

        if last_update and last_update.project_tracking_report_line_ids:
            # Copy from the last update
            for line in last_update.project_tracking_report_line_ids:
                lines_to_create.append({
                    'project_update_id': self.id,
                    'department': line.department,
                    'requirement': line.requirement,
                    'subrequirement': line.subrequirement,
                    'lot_number': line.lot_number,
                    'design_implementation_percentage': line.design_implementation_percentage,
                    'validation_percentage': line.validation_percentage,
                    'integration_percentage': line.integration_percentage,
                    'mep_planned_date': line.mep_planned_date,
                    'mep_actual_date': line.mep_actual_date,
                    'delivery_planned_date': line.delivery_planned_date,
                    'delivery_actual_date': line.delivery_actual_date,
                    'comments': line.comments
                })
        else:
            # Create new lines from project requirements and their subrequirement lines
            # Pre-fetch all lots for the project
            project_lots = self.env['project.department.lot'].search([('project_id', '=', project.id)])
            department_to_lot_map = {}
            for lot in project_lots:
                for dept in lot.department_ids:
                    department_to_lot_map[dept.id] = lot

            # Helper function to create a tracking line
            def add_tracking_line(department, requirement_name, subrequirement_name='',
                                  requirement_id=False, subrequirement_id=False):
                if not requirement_name:
                    return

                department_lot = department_to_lot_map.get(department.id) if department else None

                line_vals = {
                    'project_update_id': self.id,
                    'department': department.name if department else '',
                    'requirement': requirement_name,
                    'subrequirement': subrequirement_name,
                    'lot_number': department_lot.name if department_lot else '',
                    # Initialize percentages
                    'design_implementation_percentage': 0,
                    'validation_percentage': 0,
                    'integration_percentage': 0,
                    # Get planned dates from the department's lot
                    'delivery_planned_date': department_lot.delivery_planned_date if department_lot else None,
                    'mep_planned_date': department_lot.mep_planned_date if department_lot else None,
                    # Initialize actual dates and comments
                    'mep_actual_date': None,
                    'delivery_actual_date': None,
                    'comments': ''
                }

                # Add requirement/subrequirement IDs if provided
                if requirement_id:
                    line_vals['requirement_line_id'] = requirement_id
                if subrequirement_id:
                    line_vals['subrequirement_line_id'] = subrequirement_id

                lines_to_create.append(line_vals)

            # Determine project type: does it use custom requirements?
            # For now we determine if the project is a custom requirement project by checking if it has custom requirement lines
            is_custom_requirement_project = (
                    hasattr(project, 'custom_requirement_line_ids') and
                    bool(project.custom_requirement_line_ids)
            )

            if is_custom_requirement_project:
                # Process custom requirement lines for projects that use them
                for custom_req_line in project.custom_requirement_line_ids:
                    department = custom_req_line.department_id
                    main_requirement_name = custom_req_line.name or ''

                    # For custom requirements, check if they have subrequirement lines
                    if hasattr(custom_req_line,
                               'custom_subrequirement_line_ids') and custom_req_line.custom_subrequirement_line_ids:
                        # Process subrequirement lines
                        for sub_req_line in custom_req_line.custom_subrequirement_line_ids:
                            # Use the subrequirement field directly instead of name or description
                            subrequirement_name = sub_req_line.name or ''

                            add_tracking_line(
                                department,
                                main_requirement_name,
                                subrequirement_name
                            )
                    else:
                        # If no subrequirement lines, create a tracking line for the requirement itself
                        add_tracking_line(department, main_requirement_name)
            else:
                # Process standard requirement lines for traditional projects
                for req_line in project.requirement_line_ids:
                    department = req_line.department_id
                    requirement = req_line.requirement_id
                    main_requirement_name = requirement.name if requirement else ''

                    if not req_line.subrequirement_line_ids:
                        # Skip requirement lines without subrequirement lines
                        continue

                    for sub_req_line in req_line.subrequirement_line_ids:
                        subrequirement_name = sub_req_line.subrequirement_id.description if sub_req_line.subrequirement_id else ''
                        add_tracking_line(
                            department,
                            main_requirement_name,
                            subrequirement_name,
                            req_line.id,
                            sub_req_line.id
                        )

        if lines_to_create:
            TrackingLine.create(lines_to_create)
