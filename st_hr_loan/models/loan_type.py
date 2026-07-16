from odoo import fields, models

class StHrLoanType(models.Model):
    _name = 'st.hr.loan.type'
    _description = 'HR Loan Type'

    name = fields.Char(required=True)
    interest_rate = fields.Float(string='Interest Rate (%)')
    max_amount = fields.Float(
        string='Maximum Loan Amount',
        help='Maximum amount an employee can request for this loan type. '
             'Leave 0 for no limit.')

    required_document_ids = fields.One2many(
        'st.hr.loan.type.document', 'loan_type_id', string='Required Documents')

    is_salary_advance = fields.Boolean(
        string='Is Salary Advance',
        default=False)

    # _sql_constraints = [
    #     ('loan_type_name_unique',
    #      'unique(name)',
    #      'Loan Type already exists.')
    # ]


