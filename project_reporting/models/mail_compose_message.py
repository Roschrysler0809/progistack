from odoo import models,fields


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(string='CC')

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

    def get_mail_values(self, res_ids):
        mail_values = super().get_mail_values(res_ids)
        for res_id in res_ids:
            if self.email_cc:
                mail_values[res_id]['email_cc'] = self.email_cc
        return mail_values

