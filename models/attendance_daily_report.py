# -*- coding: utf-8 -*-
import datetime
import logging
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def format_duration(hours_float):
    """Format float hours into compact '{h}h{m}m', '{h}h', or '{m}m' string"""
    if not hours_float or hours_float <= 0:
        return ""
    total_m = int(round(hours_float * 60))
    h = total_m // 60
    m = total_m % 60
    if h > 0 and m > 0:
        return f"{h}h{m}m"
    elif h > 0 and m == 0:
        return f"{h}h"
    elif h == 0 and m > 0:
        return f"{m}m"
    return ""


class InfsAttendanceDailyDigest(models.TransientModel):
    """Model to generate, compile, and send the Daily Attendance Email Digest with Weekly Grid"""
    _name = 'infs.attendance.daily.digest'
    _description = 'Daily Attendance Email Digest Generator'

    @api.model
    def get_weekly_report_url(self):
        """Generate direct URL pointing to the Weekly Attendance Matrix Report in Odoo"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        try:
            action = self.env.ref('infs_attendance.action_infs_attendance_weekly_report_viewer_server')
            action_id = action.id if action else ''
        except Exception:
            action_id = ''

        if action_id:
            return f"{base_url.rstrip('/')}/web#action={action_id}"
        return f"{base_url.rstrip('/')}/web"

    @api.model
    def compile_attendance_digest_data(self, company, target_date=None):
        """Compile weekly grid attendance data (Sun to Sat) for the email template"""
        tz_name = company.attendance_report_tz or self.env.user.tz or 'Asia/Bangkok'
        local_tz = pytz.timezone(tz_name)

        if not target_date:
            now_local = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(local_tz)
            today_date = now_local.date()
        else:
            today_date = target_date

        yesterday_date = today_date - datetime.timedelta(days=1)

        # Calculate Sunday start and Saturday end dates
        days_since_sun = (today_date.weekday() + 1) % 7
        sun_date = today_date - datetime.timedelta(days=days_since_sun)
        sat_date = sun_date + datetime.timedelta(days=6)

        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        week_days = []
        for i, name in enumerate(day_names):
            d = sun_date + datetime.timedelta(days=i)
            week_days.append({
                'name': name,
                'date_str': d.strftime('%Y-%m-%d'),
                'date': d,
                'is_today': (d == today_date),
            })

        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', company.id)
        ], order='department_id, name')

        # Time range in UTC for the entire week
        week_start_local = local_tz.localize(datetime.datetime.combine(sun_date, datetime.time.min))
        week_end_local = local_tz.localize(datetime.datetime.combine(sat_date, datetime.time.max))
        week_start_utc = week_start_local.astimezone(pytz.utc).replace(tzinfo=None)
        week_end_utc = week_end_local.astimezone(pytz.utc).replace(tzinfo=None)

        week_attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', week_start_utc),
            ('check_in', '<=', week_end_utc),
        ], order='check_in asc')

        # Group attendances by (employee_id, local_date)
        att_map = {}
        for att in week_attendances:
            check_in_local = pytz.utc.localize(att.check_in).astimezone(local_tz)
            att_date = check_in_local.date()
            key = (att.employee_id.id, att_date)
            if key not in att_map:
                att_map[key] = []
            att_map[key].append(att)

        # Build Employee Weekly Matrix Rows
        employee_rows = []
        yest_missed_count = 0
        today_checked_in_count = 0

        for emp in employees:
            emp_days = []

            for wday in week_days:
                d = wday['date']
                day_atts = att_map.get((emp.id, d), [])

                in_str = ""
                out_str = ""
                hrs_str = ""
                in_color = "#333333"
                out_color = "#333333"
                hrs_color = "#333333"

                if day_atts:
                    # In Time
                    first_in_utc = day_atts[0].check_in
                    first_in_local = pytz.utc.localize(first_in_utc).astimezone(local_tz)
                    in_str = first_in_local.strftime('%H:%M')

                    # Flag late check-in in red (e.g. after 09:30)
                    if (first_in_local.hour > 9) or (first_in_local.hour == 9 and first_in_local.minute > 30):
                        in_color = "#c5221f"

                    if d == today_date:
                        today_checked_in_count += 1

                    # Out Time
                    last_out_atts = [a for a in day_atts if a.check_out]
                    if last_out_atts:
                        last_out_utc = last_out_atts[-1].check_out
                        last_out_local = pytz.utc.localize(last_out_utc).astimezone(local_tz)
                        out_str = last_out_local.strftime('%H:%M')
                        # Flag early departure in red (e.g. before 17:00 on weekdays)
                        if d.weekday() < 5 and last_out_local.hour < 17:
                            out_color = "#c5221f"
                    else:
                        out_str = ""
                        if d < today_date:
                            # Missed checkout on past days
                            out_color = "#c5221f"
                            if d == yesterday_date:
                                yest_missed_count += 1

                    # Total Worked Hours
                    day_hours = sum(a.worked_hours for a in day_atts if a.worked_hours)
                    if day_hours > 0:
                        hrs_str = format_duration(day_hours)
                        # Color coding: Green if >= 9h30m, Red if < 9h (on completed past shifts)
                        if day_hours >= 9.5:
                            hrs_color = "#137333"
                        elif day_hours < 9.0 and last_out_atts and d.weekday() < 5:
                            hrs_color = "#c5221f"

                emp_days.append({
                    'in': in_str,
                    'out': out_str,
                    'hrs': hrs_str,
                    'in_color': in_color,
                    'out_color': out_color,
                    'hrs_color': hrs_color,
                })

            employee_rows.append({
                'name': emp.name,
                'department': emp.department_id.name or '',
                'days': emp_days,
            })

        return {
            'company': company,
            'week_start_str': sun_date.strftime('%Y-%m-%d'),
            'week_end_str': sat_date.strftime('%Y-%m-%d'),
            'today_date_str': today_date.strftime('%A, %b %d, %Y'),
            'week_days': week_days,
            'total_employees': len(employees),
            'today_checked_in': today_checked_in_count,
            'today_not_checked_in': len(employees) - today_checked_in_count,
            'yesterday_missed_checkout': yest_missed_count,
            'employee_rows': employee_rows,
            'weekly_report_url': self.get_weekly_report_url(),
        }

    @api.model
    def send_daily_attendance_digest(self, company, is_test=False, custom_recipients=None):
        """Send the daily attendance email digest to configured or custom recipients"""
        # Refresh current week's grid data so the link points to up-to-date data
        self.env['infs.attendance.weekly.report'].refresh_weekly_data()

        digest_data = self.compile_attendance_digest_data(company)

        # Collect recipient emails
        recipients = set()
        if custom_recipients:
            for r in custom_recipients:
                if r and r.strip():
                    recipients.add(r.strip())
        else:
            for partner in company.attendance_report_recipient_ids:
                if partner.email:
                    recipients.add(partner.email.strip())
            if company.attendance_report_extra_emails:
                for email in company.attendance_report_extra_emails.split(','):
                    if email.strip():
                        recipients.add(email.strip())

        if not recipients:
            _logger.warning("No recipients configured for daily attendance report in company %s", company.name)
            if is_test:
                raise UserError(_("No recipient email found. Please configure recipients in Settings."))
            return False

        email_to_str = ','.join(recipients)

        template = self.env.ref('infs_attendance.email_template_daily_attendance_digest', raise_if_not_found=False)
        if not template:
            _logger.error("Email template 'infs_attendance.email_template_daily_attendance_digest' not found.")
            return False

        # Prepare context values for template rendering
        ctx = {
            'digest': digest_data,
            'email_to': email_to_str,
            'company_name': company.name,
            'subject_date': digest_data['today_date_str'],
        }

        template.with_context(ctx).send_mail(
            company.id,
            force_send=True,
            email_values={'email_to': email_to_str}
        )
        _logger.info("Daily attendance digest email sent to: %s", email_to_str)
        return True

    @api.model
    def _cron_send_daily_attendance_report(self):
        """Scheduled Action to trigger daily email digest at configured send_time"""
        companies = self.env['res.company'].search([('enable_attendance_daily_report', '=', True)])

        for company in companies:
            tz_name = company.attendance_report_tz or 'Asia/Bangkok'
            try:
                local_tz = pytz.timezone(tz_name)
            except Exception:
                local_tz = pytz.timezone('Asia/Bangkok')

            now_local = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(local_tz)
            today_date = now_local.date()
            current_hour_float = now_local.hour + (now_local.minute / 60.0)

            # Check if last sent was today
            last_sent = company.last_daily_report_sent_date
            if last_sent == today_date:
                continue

            target_send_time = company.attendance_report_send_time or 10.0

            # Send if current local time is at or after target_send_time
            if current_hour_float >= target_send_time:
                try:
                    self.send_daily_attendance_digest(company)
                    company.sudo().write({'last_daily_report_sent_date': today_date})
                except Exception as err:
                    _logger.error("Error sending daily attendance digest for company %s: %s", company.name, err)
