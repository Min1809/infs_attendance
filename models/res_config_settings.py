# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.base.models.res_partner import _tz_get


def _get_friendly_timezones(self):
    """Return common regional timezones with clear labels at top, followed by all timezones"""
    priority_tz = [
        ('Asia/Bangkok', 'Thailand (UTC+7:00 Bangkok / Indochina)'),
        ('Asia/Yangon', 'Myanmar (UTC+6:30 Yangon)'),
        ('Asia/Jakarta', 'Indonesia (UTC+7:00 Jakarta)'),
        ('Asia/Singapore', 'Singapore / Malaysia (UTC+8:00)'),
        ('Asia/Ho_Chi_Minh', 'Vietnam (UTC+7:00 Ho Chi Minh)'),
        ('Asia/Tokyo', 'Japan (UTC+9:00 Tokyo)'),
        ('Asia/Dubai', 'UAE (UTC+4:00 Dubai)'),
        ('Europe/London', 'UK / GMT (UTC+0 / UTC+1)'),
        ('America/New_York', 'US Eastern (UTC-5 / UTC-4)'),
        ('UTC', 'UTC (Coordinated Universal Time)'),
    ]
    seen = {k for k, _ in priority_tz}
    all_tz = _tz_get(self)
    remaining = [(k, v) for k, v in all_tz if k not in seen]
    return priority_tz + remaining


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_attendance_daily_report = fields.Boolean(
        string="Enable Daily Attendance Email Report",
        default=True,
        help="Automatically send a daily email digest of yesterday's checkout and today's morning check-in."
    )
    attendance_report_recipient_ids = fields.Many2many(
        'res.partner',
        'company_attendance_report_partner_rel',
        'company_id',
        'partner_id',
        string="Report Recipients",
        help="Partners / Users who will receive the daily attendance digest."
    )
    attendance_report_extra_emails = fields.Char(
        string="Additional Email Addresses",
        help="Additional comma-separated email addresses (e.g. hr@company.com, manager@company.com)."
    )
    attendance_report_send_time = fields.Float(
        string="Daily Send Time (Local)",
        default=10.0,
        help="Time of day to send the email report in local timezone (e.g. 10.0 = 10:00 AM, 9.5 = 9:30 AM)."
    )
    attendance_report_tz = fields.Selection(
        selection=_get_friendly_timezones,
        string="Report Timezone",
        default=lambda self: self.env.user.tz or self.partner_id.tz or 'Asia/Bangkok',
        help="Local timezone used to determine the morning send schedule and dates."
    )
    last_daily_report_sent_date = fields.Date(
        string="Last Daily Report Sent Date",
        help="Keeps track of when the report was last sent to prevent duplicate emails."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_attendance_daily_report = fields.Boolean(
        related='company_id.enable_attendance_daily_report',
        readonly=False,
        string="Enable Daily Attendance Email Report"
    )
    attendance_report_recipient_ids = fields.Many2many(
        related='company_id.attendance_report_recipient_ids',
        readonly=False,
        string="Report Recipients"
    )
    attendance_report_extra_emails = fields.Char(
        related='company_id.attendance_report_extra_emails',
        readonly=False,
        string="Additional Email Addresses"
    )
    attendance_report_send_time = fields.Float(
        related='company_id.attendance_report_send_time',
        readonly=False,
        string="Daily Send Time (Local)"
    )
    attendance_report_tz = fields.Selection(
        related='company_id.attendance_report_tz',
        readonly=False,
        string="Report Timezone"
    )

    def action_send_test_daily_report(self):
        """Send immediate test email to configured recipients (or current user if none configured)"""
        self.ensure_one()

        # Collect all configured recipient emails
        recipients = set()
        for partner in self.attendance_report_recipient_ids:
            if partner.email:
                recipients.add(partner.email.strip())
        if self.attendance_report_extra_emails:
            for email in self.attendance_report_extra_emails.split(','):
                if email.strip():
                    recipients.add(email.strip())

        # If no recipients are configured yet, fall back to current user's email
        if not recipients:
            current_email = self.env.user.email or self.env.user.partner_id.email
            if current_email:
                recipients.add(current_email.strip())
            else:
                raise UserError(_("Please configure at least one recipient or ensure your user profile has an email address."))

        self.env['infs.attendance.daily.digest'].send_daily_attendance_digest(
            self.company_id,
            is_test=True,
            custom_recipients=list(recipients)
        )

        sent_to_str = ', '.join(recipients)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test Email Sent'),
                'message': _('Daily Attendance Digest email has been sent to: %s') % sent_to_str,
                'type': 'success',
                'sticky': False,
            }
        }
