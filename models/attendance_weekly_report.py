# -*- coding: utf-8 -*-
import datetime
import pytz
from odoo import api, fields, models, _


class InfsAttendanceWeeklyReport(models.Model):
    """Weekly Attendance Grid Report (Sunday to Saturday)"""
    _name = 'infs.attendance.weekly.report'
    _description = 'Weekly Attendance Report (Sun - Sat)'
    _order = 'department_id, employee_id'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, ondelete='cascade')
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, string="Department")
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True, string="Job Position")

    week_start_date = fields.Date(string="Week Start (Sunday)", required=True, index=True)
    week_end_date = fields.Date(string="Week End (Saturday)", required=True, index=True)

    # Sunday
    sun_date = fields.Date(string="Sun Date")
    sun_in = fields.Char(string="Sun In", default="-")
    sun_out = fields.Char(string="Sun Out", default="-")
    sun_hours = fields.Float(string="Sun (Hrs)", default=0.0)

    # Monday
    mon_date = fields.Date(string="Mon Date")
    mon_in = fields.Char(string="Mon In", default="-")
    mon_out = fields.Char(string="Mon Out", default="-")
    mon_hours = fields.Float(string="Mon (Hrs)", default=0.0)

    # Tuesday
    tue_date = fields.Date(string="Tue Date")
    tue_in = fields.Char(string="Tue In", default="-")
    tue_out = fields.Char(string="Tue Out", default="-")
    tue_hours = fields.Float(string="Tue (Hrs)", default=0.0)

    # Wednesday
    wed_date = fields.Date(string="Wed Date")
    wed_in = fields.Char(string="Wed In", default="-")
    wed_out = fields.Char(string="Wed Out", default="-")
    wed_hours = fields.Float(string="Wed (Hrs)", default=0.0)

    # Thursday
    thu_date = fields.Date(string="Thu Date")
    thu_in = fields.Char(string="Thu In", default="-")
    thu_out = fields.Char(string="Thu Out", default="-")
    thu_hours = fields.Float(string="Thu (Hrs)", default=0.0)

    # Friday
    fri_date = fields.Date(string="Fri Date")
    fri_in = fields.Char(string="Fri In", default="-")
    fri_out = fields.Char(string="Fri Out", default="-")
    fri_hours = fields.Float(string="Fri (Hrs)", default=0.0)

    # Saturday
    sat_date = fields.Date(string="Sat Date")
    sat_in = fields.Char(string="Sat In", default="-")
    sat_out = fields.Char(string="Sat Out", default="-")
    sat_hours = fields.Float(string="Sat (Hrs)", default=0.0)

    total_hours = fields.Float(string="Total Hours", default=0.0)

    @api.model
    def get_week_bounds(self, target_date=None):
        """Calculate Sunday start and Saturday end dates for given target_date"""
        if not target_date:
            target_date = fields.Date.context_today(self)
        elif isinstance(target_date, str):
            target_date = fields.Date.from_string(target_date)

        days_since_sun = (target_date.weekday() + 1) % 7
        sun_date = target_date - datetime.timedelta(days=days_since_sun)
        sat_date = sun_date + datetime.timedelta(days=6)
        return sun_date, sat_date

    @api.model
    def refresh_weekly_data(self, target_date=None):
        """Compute and update the weekly grid for all active employees"""
        sun_date, sat_date = self.get_week_bounds(target_date)

        tz_name = self.env.user.tz or self.env.company.partner_id.tz or 'Asia/Bangkok'
        local_tz = pytz.timezone(tz_name)

        employees = self.env['hr.employee'].sudo().search([('active', '=', True)], order='department_id, name')

        start_local = local_tz.localize(datetime.datetime.combine(sun_date, datetime.time.min))
        end_local = local_tz.localize(datetime.datetime.combine(sat_date, datetime.time.max))
        start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(pytz.utc).replace(tzinfo=None)

        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], order='check_in asc')

        att_map = {}
        for att in attendances:
            check_in_local = pytz.utc.localize(att.check_in).astimezone(local_tz)
            att_date = check_in_local.date()
            key = (att.employee_id.id, att_date)
            if key not in att_map:
                att_map[key] = []
            att_map[key].append(att)

        self.search([('week_start_date', '=', sun_date)]).unlink()

        day_prefixes = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
        records_to_create = []

        for emp in employees:
            vals = {
                'employee_id': emp.id,
                'week_start_date': sun_date,
                'week_end_date': sat_date,
                'total_hours': 0.0,
            }

            emp_total_hours = 0.0

            for i, prefix in enumerate(day_prefixes):
                cur_date = sun_date + datetime.timedelta(days=i)
                vals[f'{prefix}_date'] = cur_date

                day_atts = att_map.get((emp.id, cur_date), [])
                if day_atts:
                    first_in_utc = day_atts[0].check_in
                    first_in_local = pytz.utc.localize(first_in_utc).astimezone(local_tz)
                    vals[f'{prefix}_in'] = first_in_local.strftime('%H:%M')

                    last_out_att = [a for a in day_atts if a.check_out]
                    if last_out_att:
                        last_out_utc = last_out_att[-1].check_out
                        last_out_local = pytz.utc.localize(last_out_utc).astimezone(local_tz)
                        vals[f'{prefix}_out'] = last_out_local.strftime('%H:%M')
                    else:
                        vals[f'{prefix}_out'] = 'Active' if cur_date == fields.Date.context_today(self) else 'Missed'

                    day_hours = sum(a.worked_hours for a in day_atts if a.worked_hours)
                    vals[f'{prefix}_hours'] = round(day_hours, 2)
                    emp_total_hours += day_hours
                else:
                    vals[f'{prefix}_in'] = '-'
                    vals[f'{prefix}_out'] = '-'
                    vals[f'{prefix}_hours'] = 0.0

            vals['total_hours'] = round(emp_total_hours, 2)
            records_to_create.append(vals)

        if records_to_create:
            self.create(records_to_create)

        return sun_date, sat_date

    @api.model
    def action_open_weekly_report(self, target_date=None):
        """Action to refresh and display the weekly attendance report"""
        sun_date, sat_date = self.refresh_weekly_data(target_date)
        action = self.env["ir.actions.actions"]._for_xml_id("infs_attendance.action_infs_attendance_weekly_report_window")
        action['domain'] = [('week_start_date', '=', sun_date)]
        action['context'] = {
            'search_default_week_start_date': str(sun_date),
            'default_week_start_date': str(sun_date),
            'default_week_end_date': str(sat_date),
        }
        action['display_name'] = _('Weekly Attendance (%s to %s)') % (sun_date.strftime('%b %d'), sat_date.strftime('%b %d, %Y'))
        return action

    def action_prev_week(self):
        """Navigate to previous week"""
        current_sun = self.week_start_date or fields.Date.context_today(self)
        prev_target = current_sun - datetime.timedelta(days=7)
        return self.env['infs.attendance.weekly.report'].action_open_weekly_report(prev_target)

    def action_next_week(self):
        """Navigate to next week"""
        current_sun = self.week_start_date or fields.Date.context_today(self)
        next_target = current_sun + datetime.timedelta(days=7)
        return self.env['infs.attendance.weekly.report'].action_open_weekly_report(next_target)

    def action_current_week(self):
        """Navigate to current week"""
        return self.env['infs.attendance.weekly.report'].action_open_weekly_report(fields.Date.context_today(self))

    def action_refresh_current_view(self):
        """Refresh current week data"""
        target = self.week_start_date if self else fields.Date.context_today(self)
        return self.env['infs.attendance.weekly.report'].action_open_weekly_report(target)


class InfsAttendanceWeeklyReportViewer(models.TransientModel):
    """Interactive Weekly Attendance Grid Report Viewer with 3-tier Header Matrix"""
    _name = 'infs.attendance.weekly.report.viewer'
    _description = 'Weekly Attendance Report Matrix Viewer'

    name = fields.Char(string="Name", compute='_compute_display_name', store=False)
    target_date = fields.Date(string="Target Week", default=fields.Date.context_today, required=True)
    department_id = fields.Many2one('hr.department', string="Department Filter")

    week_start_date = fields.Date(string="Week Start", compute='_compute_report_data')
    week_end_date = fields.Date(string="Week End", compute='_compute_report_data')
    week_label = fields.Char(string="Week Range", compute='_compute_report_data')

    total_employees = fields.Integer(string="Total Staff", compute='_compute_report_data')
    today_checked_in = fields.Integer(string="Checked In Today", compute='_compute_report_data')
    yesterday_missed = fields.Integer(string="Missed Checkout", compute='_compute_report_data')

    html_table = fields.Html(string="Weekly Attendance Matrix", compute='_compute_report_data', sanitize=False)

    @api.depends('week_label', 'target_date')
    def _compute_display_name(self):
        for rec in self:
            label = rec.week_label
            if not label and rec.target_date:
                days_since_sun = (rec.target_date.weekday() + 1) % 7
                sun_date = rec.target_date - datetime.timedelta(days=days_since_sun)
                sat_date = sun_date + datetime.timedelta(days=6)
                label = f"{sun_date.strftime('%a, %b %d')} - {sat_date.strftime('%a, %b %d, %Y')}"
            disp = f"Weekly Attendance ({label})" if label else _("Weekly Attendance Summary")
            rec.display_name = disp
            rec.name = disp

    @api.depends('target_date', 'department_id')
    def _compute_report_data(self):
        for rec in self:
            target_date = rec.target_date or fields.Date.context_today(rec)

            days_since_sun = (target_date.weekday() + 1) % 7
            sun_date = target_date - datetime.timedelta(days=days_since_sun)
            sat_date = sun_date + datetime.timedelta(days=6)

            rec.week_start_date = sun_date
            rec.week_end_date = sat_date
            rec.week_label = f"{sun_date.strftime('%a, %b %d')} - {sat_date.strftime('%a, %b %d, %Y')}"

            tz_name = rec.env.user.tz or rec.env.company.attendance_report_tz or 'Asia/Bangkok'
            try:
                local_tz = pytz.timezone(tz_name)
            except Exception:
                local_tz = pytz.timezone('Asia/Bangkok')

            now_local = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(local_tz)
            today_date = now_local.date()
            yesterday_date = today_date - datetime.timedelta(days=1)

            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            week_days = []
            for i, name in enumerate(day_names):
                d = sun_date + datetime.timedelta(days=i)
                week_days.append({
                    'name': name,
                    'date': d,
                    'date_str': d.strftime('%Y-%m-%d'),
                    'is_today': (d == today_date),
                    'is_weekend': (i == 0 or i == 6),
                })

            domain = [('active', '=', True)]
            if rec.department_id:
                domain.append(('department_id', '=', rec.department_id.id))

            employees = rec.env['hr.employee'].sudo().search(domain, order='department_id, name')
            rec.total_employees = len(employees)

            week_start_local = local_tz.localize(datetime.datetime.combine(sun_date, datetime.time.min))
            week_end_local = local_tz.localize(datetime.datetime.combine(sat_date, datetime.time.max))
            week_start_utc = week_start_local.astimezone(pytz.utc).replace(tzinfo=None)
            week_end_utc = week_end_local.astimezone(pytz.utc).replace(tzinfo=None)

            attendances = rec.env['hr.attendance'].sudo().search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', week_start_utc),
                ('check_in', '<=', week_end_utc),
            ], order='check_in asc')

            att_map = {}
            for att in attendances:
                check_in_local = pytz.utc.localize(att.check_in).astimezone(local_tz)
                att_date = check_in_local.date()
                key = (att.employee_id.id, att_date)
                if key not in att_map:
                    att_map[key] = []
                att_map[key].append(att)

            today_checked_in_count = 0
            yest_missed_count = 0

            html_rows = []
            day_total_hours = [0.0] * 7
            grand_total_hours = 0.0

            for emp in employees:
                emp_total_hours = 0.0
                day_cells = []

                for idx, wday in enumerate(week_days):
                    d = wday['date']
                    day_atts = att_map.get((emp.id, d), [])
                    in_str = "-"
                    out_str = "-"
                    hrs_str = "-"
                    in_color = "#333333"
                    out_color = "#333333"
                    hrs_color = "#333333"
                    bg_color = "#f8fafc" if wday['is_weekend'] else "#ffffff"

                    if day_atts:
                        first_in_utc = day_atts[0].check_in
                        first_in_local = pytz.utc.localize(first_in_utc).astimezone(local_tz)
                        in_str = first_in_local.strftime('%H:%M')

                        if (first_in_local.hour > 9) or (first_in_local.hour == 9 and first_in_local.minute > 30):
                            in_color = "#c5221f"

                        if d == today_date:
                            today_checked_in_count += 1

                        last_out_atts = [a for a in day_atts if a.check_out]
                        if last_out_atts:
                            last_out_utc = last_out_atts[-1].check_out
                            last_out_local = pytz.utc.localize(last_out_utc).astimezone(local_tz)
                            out_str = last_out_local.strftime('%H:%M')
                            if d.weekday() < 5 and last_out_local.hour < 17:
                                out_color = "#c5221f"
                        else:
                            out_str = "Active" if d == today_date else "Missed"
                            out_color = "#137333" if d == today_date else "#c5221f"
                            if d == yesterday_date:
                                yest_missed_count += 1

                        day_hours = sum(a.worked_hours for a in day_atts if a.worked_hours)
                        if day_hours > 0:
                            hrs_str = f"{day_hours:.2f}h"
                            emp_total_hours += day_hours
                            day_total_hours[idx] += day_hours
                            if day_hours >= 9.5:
                                hrs_color = "#137333"
                            elif day_hours < 8.0 and last_out_atts and d.weekday() < 5:
                                hrs_color = "#c5221f"

                    day_cells.append(f"""
                        <td style="border: 1px solid #cbd5e1; padding: 6px 6px; font-size: 11px; text-align: left; color: {in_color}; font-family: monospace, Arial; background-color: {bg_color};">{in_str}</td>
                        <td style="border: 1px solid #cbd5e1; padding: 6px 6px; font-size: 11px; text-align: left; color: {out_color}; font-family: monospace, Arial; background-color: {bg_color};">{out_str}</td>
                        <td style="border: 1px solid #cbd5e1; border-right: 2px solid #475569; padding: 6px 6px; font-size: 11px; text-align: left; font-weight: bold; color: {hrs_color}; font-family: monospace, Arial; background-color: {bg_color};">{hrs_str}</td>
                    """)

                grand_total_hours += emp_total_hours
                total_hrs_display = f"{emp_total_hours:.2f}h"
                dept_name = emp.department_id.name or '-'

                html_rows.append(f"""
                    <tr style="background-color: #ffffff;">
                        <td style="border: 1px solid #cbd5e1; padding: 6px 8px; font-size: 12px; color: #1e293b; text-align: left; font-weight: 600; white-space: nowrap;">
                            {emp.name}
                        </td>
                        <td style="border: 1px solid #cbd5e1; padding: 6px 8px; font-size: 11px; color: #64748b; text-align: left; white-space: nowrap;">
                            {dept_name}
                        </td>
                        <td style="border: 1px solid #cbd5e1; border-right: 2px solid #475569; padding: 6px 8px; font-size: 12px; text-align: left; font-weight: bold; color: #714B67; background-color: #f3e8f2; white-space: nowrap;">
                            {total_hrs_display}
                        </td>
                        {''.join(day_cells)}
                    </tr>
                """)

            rec.today_checked_in = today_checked_in_count
            rec.yesterday_missed = yest_missed_count

            # Header Row 1: Days
            header_day_cols = []
            for w in week_days:
                bg = "#e2e8f0" if w['is_weekend'] else "#f1f5f9"
                header_day_cols.append(f"""
                    <th colspan="3" style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 7px 4px; font-size: 12px; font-weight: 700; text-align: center; background-color: {bg}; color: #1e293b;">
                        {w['name']}
                    </th>
                """)

            # Header Row 2: Dates
            header_date_cols = []
            for w in week_days:
                bg = "#e2e8f0" if w['is_weekend'] else "#f1f5f9"
                today_badge = " <span style='background-color:#714B67;color:#fff;padding:1px 4px;border-radius:3px;font-size:9px;'>TODAY</span>" if w['is_today'] else ""
                header_date_cols.append(f"""
                    <th colspan="3" style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 5px 4px; font-size: 11px; font-weight: 600; text-align: center; background-color: {bg}; color: #334155;">
                        {w['date_str']}{today_badge}
                    </th>
                """)

            # Header Row 3: IN | OUT | HRS
            header_sub_cols = []
            for w in week_days:
                bg = "#f8fafc" if w['is_weekend'] else "#ffffff"
                header_sub_cols.append(f"""
                    <th style="border: 1px solid #94a3b8; padding: 5px 6px; font-size: 11px; font-weight: 700; text-align: left; background-color: {bg}; color: #475569; width: 44px;">IN</th>
                    <th style="border: 1px solid #94a3b8; padding: 5px 6px; font-size: 11px; font-weight: 700; text-align: left; background-color: {bg}; color: #475569; width: 44px;">OUT</th>
                    <th style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 5px 6px; font-size: 11px; font-weight: 700; text-align: left; background-color: {bg}; color: #475569; width: 48px;">HRS</th>
                """)

            # Footer Totals Row
            footer_day_cells = []
            for idx, w in enumerate(week_days):
                bg = "#e2e8f0" if w['is_weekend'] else "#f1f5f9"
                d_hrs = day_total_hours[idx]
                d_hrs_str = f"{d_hrs:.1f}h" if d_hrs > 0 else "-"
                footer_day_cells.append(f"""
                    <td colspan="2" style="border: 1px solid #94a3b8; padding: 6px 4px; font-size: 11px; text-align: left; color: #64748b; background-color: {bg}; font-weight: 600;">Total:</td>
                    <td style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 6px 6px; font-size: 11px; text-align: left; font-weight: bold; color: #1e293b; background-color: {bg};">{d_hrs_str}</td>
                """)

            grand_total_str = f"{grand_total_hours:.1f}h"

            table_html = f"""
            <div style="overflow-x: auto; width: 100%; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1.5px solid #64748b; background-color: #ffffff; margin-top: 10px;">
                <table style="width: 100%; border-collapse: separate; border-spacing: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 12px; margin: 0;">
                    <thead>
                        <tr>
                            <th rowspan="3" style="border: 1px solid #94a3b8; padding: 10px 8px; font-size: 13px; font-weight: 700; text-align: left; vertical-align: middle; min-width: 170px; background-color: #e2e8f0; color: #0f172a;">
                                Employee Name
                            </th>
                            <th rowspan="3" style="border: 1px solid #94a3b8; padding: 10px 8px; font-size: 13px; font-weight: 700; text-align: left; vertical-align: middle; min-width: 120px; background-color: #e2e8f0; color: #0f172a;">
                                Department
                            </th>
                            <th rowspan="3" style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 10px 8px; font-size: 13px; font-weight: 700; text-align: left; vertical-align: middle; min-width: 85px; background-color: #f3e8f2; color: #714B67;">
                                Total (h)
                            </th>
                            {''.join(header_day_cols)}
                        </tr>
                        <tr>
                            {''.join(header_date_cols)}
                        </tr>
                        <tr>
                            {''.join(header_sub_cols)}
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(html_rows) if html_rows else '<tr><td colspan="24" style="text-align:center;padding:24px;color:#94a3b8;font-size:14px;">No employee attendance records found for this week.</td></tr>'}
                    </tbody>
                    <tfoot>
                        <tr style="background-color: #f1f5f9; font-weight: bold;">
                            <td colspan="2" style="border: 1px solid #94a3b8; padding: 8px; font-size: 12px; text-align: left; color: #0f172a;">
                                Grand Total ({len(employees)} Staff)
                            </td>
                            <td style="border: 1px solid #94a3b8; border-right: 2px solid #475569; padding: 8px; font-size: 12px; text-align: left; color: #714B67; background-color: #f3e8f2;">
                                {grand_total_str}
                            </td>
                            {''.join(footer_day_cells)}
                        </tr>
                    </tfoot>
                </table>
            </div>
            """
            rec.html_table = table_html

    @api.model
    def action_open_weekly_viewer(self):
        """Action to launch the interactive Weekly Matrix Report viewer"""
        viewer = self.create({'target_date': fields.Date.context_today(self)})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Weekly Attendance Summary (Sun - Sat)'),
            'res_model': 'infs.attendance.weekly.report.viewer',
            'res_id': viewer.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_prev_week(self):
        """Navigate to previous week without pushing new breadcrumb"""
        target = (self.target_date or fields.Date.context_today(self)) - datetime.timedelta(days=7)
        self.write({'target_date': target})
        return True

    def action_next_week(self):
        """Navigate to next week without pushing new breadcrumb"""
        target = (self.target_date or fields.Date.context_today(self)) + datetime.timedelta(days=7)
        self.write({'target_date': target})
        return True

    def action_current_week(self):
        """Navigate to current week without pushing new breadcrumb"""
        self.write({'target_date': fields.Date.context_today(self)})
        return True

    def action_refresh(self):
        """Refresh current view without pushing new breadcrumb"""
        self.write({'target_date': self.target_date or fields.Date.context_today(self)})
        return True
