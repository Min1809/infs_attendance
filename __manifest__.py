# -*- coding: utf-8 -*-
{
    'name': "INFS Attendance Reports & Daily Digest",
    'version': "17.0.1.0.0",
    'category': "Human Resources/Attendances",
    'summary': "Automated daily attendance email digest and Weekly Grid Report (Sun-Sat) with multi-recipient settings",
    'description': """
INFS Attendance Reports & Daily Digest
=======================================
Key Features:
* **Automated Daily Email Digest**:
  - Yesterday's Check-In, Check-Out, Worked Hours, and Missed Checkout alerts.
  - Today's Morning Check-In status (as of configured send time, e.g. 10:00 AM).
  - Direct CTA button linking to the Weekly Attendance Grid Report in Odoo.
  - Configurable multiple recipients, extra email addresses, and send time.
  - Immediate "Send Test Report" button in Settings.
* **Weekly Attendance Grid Report (Sunday - Saturday)**:
  - Table view showing daily In-Time, Out-Time, and Worked Hours for each day of the week.
  - Weekly total hours calculation per employee.
  - Previous / Next / Current week navigation buttons.
    """,
    'author': "INFS",
    'website': "https://www.infs.com",
    'depends': ['hr_attendance', 'mail', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'data/cron.xml',
        'views/res_config_settings_views.xml',
        'views/attendance_weekly_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'infs_attendance/static/src/css/weekly_attendance_grid.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
