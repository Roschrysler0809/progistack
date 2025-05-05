import logging

from odoo import api, fields, models

MEETING_TYPE = [
    ('internal', 'Interne'),
    ('external', 'Externe')
]

MEETING_LOCATION = [
    ('online', 'En ligne'),
    ('not_set', 'En ligne ou Bureau')
]

MEETING_STATUS = [
    ('pending', 'En attente de validation'),
    ('validated', 'Validé'),
    ('completed', 'Terminé')
]

CR_STATUS = [
    ('not_sent', 'Mail CR non envoyé'),
    ('sent', 'Mail CR envoyé')
]

CR_KANBAN_STATE = {
    'not_sent': 'blocked',  # Red
    'sent': 'done'  # Green
}

KANBAN_STATE_COLORS = [
    ('normal', 'Gray'),
    ('done', 'Green'),
    ('blocked', 'Red')
]


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    project_id = fields.Many2one('project.project', string="Projet", tracking=True,
                                 help="Projet associé à cette réunion")

    compte_rendu_sent = fields.Boolean(string="CR envoyé", compute='_compute_compte_rendu_sent', store=True)
    compte_rendu_status = fields.Selection(CR_STATUS, string="Statut CR", default='not_sent', required=True,
                                           readonly=True, tracking=True,
                                           help="Statut d'envoi du compte rendu")

    cr_kanban_state = fields.Selection(KANBAN_STATE_COLORS, compute='_compute_cr_kanban_state', string='Kanban State')

    meeting_type = fields.Selection(MEETING_TYPE, string="Type de réunion", compute='_compute_meeting_type',
                                    store=True, readonly=True,
                                    help="Type de réunion: Interne (dans l'équipe) ou Externe (avec clients/partenaires)")

    meeting_status = fields.Selection(MEETING_STATUS, string="Statut", compute='_compute_meeting_status',
                                      store=True, help="Statut de la réunion: En attente, Validé, ou Terminé")

    meeting_location = fields.Selection(MEETING_LOCATION, string="Lieu", compute='_compute_meeting_location',
                                        store=True, readonly=True,
                                        help="Lieu de la réunion")

    validation_count = fields.Integer(string="Validations externes", compute='_compute_validation_count',
                                      store=True, help="Nombre de validations d'participants externes")

    compte_rendu_attachment_ids = fields.Many2many('ir.attachment', 'calendar_event_cr_attachment_rel',
                                                   'event_id', 'attachment_id', string="Compte-rendu",
                                                   help="Pièces jointes contenant le compte rendu (CR)")

    def get_filtered_attachments(self):
        """Return attachments related to this calendar event, excluding invitation.ics files"""
        self.ensure_one()
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', self.id),
            '|',
            ('mimetype', 'not ilike', 'text/calendar'),
            ('name', 'not ilike', '.ics')
        ])

    @api.depends('compte_rendu_status')
    def _compute_compte_rendu_sent(self):
        for record in self:
            record.compte_rendu_sent = record.compte_rendu_status == 'sent'

    @api.depends('attendee_ids', 'attendee_ids.state', 'partner_ids')
    def _compute_validation_count(self):
        """Calculate the number of validations from external participants"""
        current_company = self.env.company
        for event in self:
            # Get the organizer's partner
            organizer_partner = event.user_id.partner_id if event.user_id else False

            # Filter participants who have accepted and are external (not from current company)
            # Exclude the organizer from this count
            external_attendees = event.attendee_ids.filtered(
                lambda att: att.state == 'accepted' and
                            att.partner_id != organizer_partner and (
                                    not att.partner_id.user_ids or
                                    not att.partner_id.company_id or
                                    att.partner_id.company_id != current_company
                            )
            )
            event.validation_count = len(external_attendees)

    @api.depends('videocall_location')
    def _compute_meeting_location(self):
        """Determine meeting location based on videocall URL presence"""
        for event in self:
            if event.videocall_location:
                event.meeting_location = 'online'
            else:
                event.meeting_location = 'not_set'

    @api.depends('validation_count', 'start', 'attendee_ids', 'attendee_ids.state', 'meeting_type', 'partner_ids')
    def _compute_meeting_status(self):
        """Calculate meeting status based on date and validations"""
        now = fields.Datetime.now()
        current_company = self.env.company

        for event in self:
            # Get the organizer's partner
            organizer_partner = event.user_id.partner_id if event.user_id else False

            # If there are no attendees or partner_ids, meeting is pending
            non_organizer_attendees = event.attendee_ids.filtered(
                lambda att: att.partner_id != organizer_partner
            )
            if not non_organizer_attendees:
                event.meeting_status = 'pending'
                continue

            # Completed: Meeting date has passed
            if event.start and event.start < now:
                event.meeting_status = 'completed'
            # Validated: At least one external participant has validated
            elif event.validation_count > 0:
                event.meeting_status = 'validated'
            # For internal meetings: check if any internal participant has accepted
            elif event.meeting_type == 'internal':
                # Find internal attendees who have accepted, excluding the organizer
                internal_accepted = event.attendee_ids.filtered(
                    lambda att: att.state == 'accepted' and
                                att.partner_id != organizer_partner and
                                att.partner_id.user_ids and
                                att.partner_id.company_id and
                                att.partner_id.company_id == current_company
                )
                if internal_accepted:
                    event.meeting_status = 'validated'
                else:
                    event.meeting_status = 'pending'
            # Pending: Default state
            else:
                event.meeting_status = 'pending'

    @api.depends('compte_rendu_status')
    def _compute_cr_kanban_state(self):
        for record in self:
            record.cr_kanban_state = CR_KANBAN_STATE.get(record.compte_rendu_status, 'normal')

    @api.depends('attendee_ids', 'attendee_ids.partner_id', 'attendee_ids.partner_id.company_id', 'partner_ids',
                 'user_id')
    def _compute_meeting_type(self):
        """Determine meeting type based on participants
        - Internal: All participants are from the current company
        - External: At least one participant is not from the current company
        """
        current_company = self.env.company
        for event in self:
            # Get non-organizer attendees
            organizer_partner = event.user_id.partner_id if event.user_id else False
            non_organizer_attendees = event.attendee_ids.filtered(
                lambda att: att.partner_id != organizer_partner
            )

            # Default to internal meeting
            event.meeting_type = 'internal'

            # If no attendees besides organizer, keep as internal
            if not non_organizer_attendees:
                continue

            # Check if any external attendee exists
            external_attendees = non_organizer_attendees.filtered(
                lambda att: not att.partner_id.user_ids or
                            not att.partner_id.company_id or
                            att.partner_id.company_id != current_company
            )

            if external_attendees:
                event.meeting_type = 'external'

    def action_send_compte_rendu(self):
        """Preview the meeting report email before sending"""
        self.ensure_one()

        # Get the template
        template = self.env.ref('meeting_tracking.email_template_meeting_compte_rendu')

        # Generate the email body
        body = template._render_field(
            'body_html',
            [self.id],
            compute_lang=True
        )[self.id]

        # Get filtered attachments using the centralized method
        all_attachments = self.get_filtered_attachments()

        # Ensure we're getting all attachments, not just the most recent one
        # Log to confirm attachment count for debugging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Preparing to attach {len(all_attachments)} documents to compte rendu email")

        # Use the filtered attachments (no ICS files)
        attachment_ids = all_attachments.ids

        # Show a wizard with the preview
        return {
            'name': 'Envoyer le compte rendu',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': {
                'default_model': 'calendar.event',
                'default_res_ids': [self.id],
                'default_body': body,
                'default_subject': template._render_field('subject', [self.id])[self.id],
                'default_composition_mode': 'comment',
                'default_email_to': ','.join([att.email for att in self.attendee_ids if att.email]),
                'default_attachment_ids': attachment_ids,
                'default_template_id': template.id,
                'force_email': True,
                'mark_cr_sent': True,  # This flag will trigger mark_compte_rendu_sent after mail sending
            }
        }

    def mark_compte_rendu_sent(self):
        """Mark the meeting report as sent"""
        self.write({'compte_rendu_status': 'sent'})
        return True
