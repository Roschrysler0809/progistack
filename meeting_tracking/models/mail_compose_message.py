import logging

from odoo import models


class MailComposeMessage(models.TransientModel):
    """Extension of mail composer to handle meeting reports"""
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        """Override to mark meeting reports as sent"""
        _logger = logging.getLogger(__name__)

        # Handle meeting attachments BEFORE sending the mail
        if self._context.get('mark_cr_sent') and self.model == 'calendar.event':
            try:
                # Parse meeting IDs in a safe way
                meeting_ids = []
                if isinstance(self.res_ids, (list, tuple)):
                    meeting_ids = [int(res_id) for res_id in self.res_ids if
                                   isinstance(res_id, (int, str)) and str(res_id).isdigit()]
                elif isinstance(self.res_ids, int):
                    meeting_ids = [self.res_ids]
                elif isinstance(self.res_ids, str):
                    if self.res_ids.isdigit():
                        meeting_ids = [int(self.res_ids)]
                    else:
                        try:
                            from ast import literal_eval
                            ids_list = literal_eval(self.res_ids)
                            if isinstance(ids_list, (list, tuple)):
                                meeting_ids = [int(id) for id in ids_list if
                                               isinstance(id, (int, str)) and str(id).isdigit()]
                        except (ValueError, SyntaxError):
                            _logger.error(f"Unable to parse res_ids: {self.res_ids}")

                # Process each meeting to ensure its attachments are added to the email
                if meeting_ids:
                    for meeting_id in meeting_ids:
                        meeting = self.env['calendar.event'].browse(meeting_id)
                        all_attachments = meeting.get_filtered_attachments()
                        _logger.info(f"Found {len(all_attachments)} attachments for meeting {meeting.name}")

                        # Add each attachment to the email if not already included
                        current_attachment_ids = set(self.attachment_ids.ids)
                        for attachment in all_attachments:
                            if attachment.id not in current_attachment_ids:
                                self.write({
                                    'attachment_ids': [(4, attachment.id)]
                                })
                                current_attachment_ids.add(attachment.id)
                                _logger.info(f"Added attachment {attachment.name} to email")

                        _logger.info(
                            f"Final email for meeting {meeting.name} has {len(self.attachment_ids)} attachments")
            except Exception as e:
                _logger.error(f"Error processing attachments: {e}")

        # Call the original method to actually send the mail
        result = super()._action_send_mail(auto_commit=auto_commit)

        # After successful sending, mark the meeting report as sent
        if self._context.get('mark_cr_sent') and self.model == 'calendar.event':
            # Safely handle res_ids to ensure it's a proper list of integers
            try:
                if isinstance(self.res_ids, (list, tuple)):
                    meeting_ids = [int(res_id) for res_id in self.res_ids if
                                   isinstance(res_id, (int, str)) and str(res_id).isdigit()]
                elif isinstance(self.res_ids, int):
                    meeting_ids = [self.res_ids]
                elif isinstance(self.res_ids, str):
                    # Handle string case - could be '[1,2,3]' or single digit
                    if self.res_ids.isdigit():
                        meeting_ids = [int(self.res_ids)]
                    else:
                        # Try to safely evaluate as list, defaulting to empty list if fails
                        try:
                            from ast import literal_eval
                            ids_list = literal_eval(self.res_ids)
                            if isinstance(ids_list, (list, tuple)):
                                meeting_ids = [int(id) for id in ids_list if
                                               isinstance(id, (int, str)) and str(id).isdigit()]
                            else:
                                meeting_ids = []
                        except (ValueError, SyntaxError):
                            # If can't parse, log error and use empty list
                            _logger.error(f"Unable to parse res_ids: {self.res_ids}")
                            meeting_ids = []
                else:
                    meeting_ids = []

                _logger.info(f"Processing meeting IDs to mark as sent: {meeting_ids}")

                if meeting_ids:
                    meetings = self.env['calendar.event'].browse(meeting_ids)
                    meetings.mark_compte_rendu_sent()
                else:
                    _logger.warning("No valid meeting IDs found to mark as sent")

            except Exception as e:
                _logger.error(f"Error processing meeting IDs: {e}")

        return result
