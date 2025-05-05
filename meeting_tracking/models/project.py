import base64
import io
from datetime import datetime

import xlsxwriter

from odoo import api, fields, models


class Project(models.Model):
    _inherit = 'project.project'

    meeting_count = fields.Integer(string="Réunions", compute='_compute_meeting_count',
                                   help="Nombre de réunions liées à ce projet")

    @api.depends('name')
    def _compute_meeting_count(self):
        """Count the number of meetings linked to this project"""
        for project in self:
            project.meeting_count = self.env['calendar.event'].search_count([
                ('project_id', '=', project.id)
            ])

    def action_view_meetings(self):
        """Action to display meetings linked to this project"""
        self.ensure_one()

        # Get meetings linked to this project
        meetings = self.env['calendar.event'].search([
            ('project_id', '=', self.id)
        ])

        # Define the action
        action = {
            'name': 'Réunions du projet',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'context': {'default_project_id': self.id},
        }

        # Set display mode based on number of meetings
        if len(meetings) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': meetings.id,
            })
        else:
            action.update({
                'view_mode': 'list,calendar,form',
                'domain': [('id', 'in', meetings.ids)],
            })

        return action

    def action_print_meeting_report(self):
        """Generate Excel report of project meetings using xlsxwriter, mirroring meeting_report.py logic."""
        self.ensure_one()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        # Use project name in sheet name, limited length
        sheet_name = f"Réunions - {self.name}" if self.name else "Réunions"
        worksheet = workbook.add_worksheet(sheet_name)

        base_format_dict = {
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'indent': 1,
        }
        base_format = workbook.add_format(base_format_dict)

        header_format = workbook.add_format({
            **base_format_dict,
            'bold': True,
            'bg_color': '#007A77',  # ProgiStack green color
            'color': 'white',
            'text_wrap': True,
        })

        cell_format = workbook.add_format(base_format_dict)

        wrap_format = workbook.add_format({
            **base_format_dict,
            'text_wrap': True,
        })

        date_format = workbook.add_format({
            **base_format_dict,
            'num_format': 'dd/mm/yyyy',
        })

        time_format = workbook.add_format({  # Added time format
            **base_format_dict,
            'num_format': 'hh:mm',
        })

        cr_yes_format = workbook.add_format({
            **base_format_dict,
            'color': 'green',
            'bold': True,
        })

        cr_no_format = workbook.add_format({
            **base_format_dict,
            'color': 'red',
            'bold': True,
        })

        status_pending_format = workbook.add_format({
            **base_format_dict,
            'bg_color': '#FFA500',  # Orange for pending
            'color': 'black',
        })

        status_validated_format = workbook.add_format({
            **base_format_dict,
            'bg_color': '#28a745',  # Green for validated
            'color': 'black',
        })

        status_completed_format = workbook.add_format({
            **base_format_dict,
            'bg_color': '#17a2b8',  # Blue for completed
            'color': 'black',
        })

        # URL Format for attachments (using base_format for simplicity in this context)
        # We won't generate clickable URLs here, just list names.
        attachment_format = workbook.add_format({
            **base_format_dict,
            'text_wrap': True,
        })

        worksheet.set_column('A:A', 40)  # Subject
        worksheet.set_column('B:B', 15)  # Date
        worksheet.set_column('C:C', 10)  # Time
        worksheet.set_column('D:D', 20)  # Location
        worksheet.set_column('E:E', 25)  # Status
        worksheet.set_column('F:F', 60)  # Description
        worksheet.set_column('G:G', 40)  # Participants
        worksheet.set_column('H:H', 40)  # Compte rendu attachments
        worksheet.set_column('I:I', 20)  # CR envoyé

        headers = [
            'Sujet', 'Date', 'Heure', 'Lieu', 'Statut',
            'Description', 'Participants', 'Compte rendu', 'CR envoyé'
        ]
        worksheet.set_row(0, 40)  # Set header row height
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        meetings = self.env['calendar.event'].search([
            ('project_id', '=', self.id)
        ], order='start desc')  # Added order desc

        row = 1
        # Prepare mappings once if possible
        try:
            status_mapping = dict(self.env['calendar.event']._fields['meeting_status'].selection)
        except KeyError:
            status_mapping = {}  # Handle case where field might not exist

        location_mapping = {
            'online': 'En ligne',
            'not_set': 'En ligne ou Bureau'
        }

        for meeting in meetings:
            # Format participant list using attendee_ids
            attendees = ', '.join([
                att.partner_id.name for att in meeting.attendee_ids
                if att.partner_id and att.partner_id.name
            ])

            # Get display name for location
            location_display = location_mapping.get(meeting.meeting_location,
                                                    meeting.location or '')  # Use meeting.location as fallback

            # Get display name for status
            status_display = status_mapping.get(meeting.meeting_status, '')

            # Separate date and time
            meeting_date = None
            meeting_time = None
            if meeting.start:
                meeting_date = meeting.start.date()
                meeting_time = meeting.start.time()

            # Default row height
            worksheet.set_row(row, 30)

            # Write meeting data cell by cell
            worksheet.write(row, 0, meeting.name or '', cell_format)  # Col A: Sujet
            worksheet.write(row, 1, meeting_date, date_format if meeting_date else cell_format)  # Col B: Date
            worksheet.write(row, 2, meeting_time,
                            time_format if meeting_time else cell_format)  # Col C: Heure - using time_format
            worksheet.write(row, 3, location_display, cell_format)  # Col D: Lieu

            # Col E: Statut (with conditional formatting)
            status_format_to_use = cell_format
            if meeting.meeting_status == 'pending':
                status_format_to_use = status_pending_format
            elif meeting.meeting_status == 'validated':
                status_format_to_use = status_validated_format
            elif meeting.meeting_status == 'completed':
                status_format_to_use = status_completed_format
            worksheet.write(row, 4, status_display, status_format_to_use)

            worksheet.write(row, 5, meeting.description or '', wrap_format)  # Col F: Description
            worksheet.write(row, 6, attendees, wrap_format)  # Col G: Participants

            # Col H: Compte rendu (list attachment names)
            attachments = meeting.compte_rendu_attachment_ids
            if attachments:
                attachment_names = [att.name for att in attachments if att.name]
                worksheet.write(row, 7, "\\n".join(attachment_names), attachment_format)
            else:
                worksheet.write(row, 7, "Aucun fichier", cell_format)

            # Col I: CR envoyé (with conditional formatting)
            if meeting.compte_rendu_sent:
                worksheet.write(row, 8, 'Oui', cr_yes_format)
            else:
                worksheet.write(row, 8, 'Non', cr_no_format)

            # Adjust row height dynamically (simplified)
            # Note: Accurate dynamic height is complex; using a fixed height or simple logic
            # For simplicity, keeping the default or a slightly larger fixed height might be best here.

            row += 1

        workbook.close()
        output.seek(0)
        excel_data = output.read()

        date_str = datetime.now().strftime('%d-%m-%Y')
        safe_project_name = (self.name or 'SansNom').replace('/', '-').strip()
        filename = f"Rapport Réunions {safe_project_name} {date_str}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(excel_data),
            'res_model': 'project.project',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
