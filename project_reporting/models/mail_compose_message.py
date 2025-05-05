from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        """Override to update project update status after sending email."""
        result = super()._action_send_mail(auto_commit=auto_commit)

        # Check if we need to mark project updates as sent
        if (self.model == 'project.update' and
                (self._context.get('mark_update_as_sent') or self._context.get('default_mark_update_as_sent')) and
                self.res_ids):

            try:
                # Convert res_ids to list of integers if needed
                ids = self.res_ids
                if isinstance(ids, str):
                    # Extract numeric IDs from string like "[1, 2, 3]"
                    ids = [int(id_str) for id_str in ids.strip('[]').split(',') if id_str.strip().isdigit()]

                if ids:
                    # Use ORM write method to ensure proper tracking and logging
                    project_updates = self.env['project.update'].browse(ids)
                    project_updates.write({'state': 'sent'})
            except (ValueError, AttributeError):
                pass

        return result
