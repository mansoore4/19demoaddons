# -*- coding: utf-8 -*-
{
    'name': 'HR Loan',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage employee loans and repayment schedules.',
    'author': 'Steigend IT Solutions',
    'description': """
          Manage employee loans, salary advances,
          approvals, disbursements, and repayment schedules.
     """,

    'depends': ['hr', 'mail'],
    'data': [

        'security/loan_security.xml',
        'security/ir.model.access.csv',
        'data/loan_sequence.xml',
        'views/loan_type_views.xml',
        'views/loan_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'website': 'https://steigendit.com/',
    'license': 'LGPL-3',
}
