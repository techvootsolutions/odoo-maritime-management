from odoo import models


class MaritimeNotificationMixin(models.AbstractModel):
    _name = 'maritime.notification.mixin'
    _description = 'Maritime Email Notification Helpers'

    def _maritime_message_post(self, body, *, partner=None, subtype_xmlid='mail.mt_comment'):
        values = {'body': body, 'subtype_xmlid': subtype_xmlid}
        if partner:
            values['partner_ids'] = partner.ids
        return self.message_post(**values)

    def _maritime_send_template(self, template_xmlid, *, partners=None, users=None):
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        if partners:
            for partner in partners.filtered('email'):
                template.send_mail(self.id, force_send=False)
        if users:
            for user in users.mapped('partner_id').filtered('email'):
                template.with_context(
                    partner_to=user.id,
                ).send_mail(self.id, force_send=False)

    def _maritime_notify_group(self, template_xmlid, group_xmlid, body=None):
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if body:
            self.message_post(body=body, subtype_xmlid='mail.mt_note')
        if group and group.user_ids:
            self._maritime_send_template(template_xmlid, users=group.user_ids)

    def _maritime_notify_partner(self, template_xmlid, partner, body=None):
        if body:
            self._maritime_message_post(body, partner=partner)
        if partner and partner.email:
            self._maritime_send_template(template_xmlid, partners=partner)
