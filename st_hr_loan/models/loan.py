# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class StHrLoan(models.Model):
    _name = 'st.hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Employee Loan / Advance'
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default='New', index=True)

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='restrict', tracking=True,
        default=lambda self: self.env.user.employee_id)

    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, readonly=True)

    loan_amount = fields.Float(
        string='Loan Amount', required=True, tracking=True,
        help='Principal amount lent to the employee.')

    loan_type_id = fields.Many2one(
        'st.hr.loan.type',
        string='Loan Type',
        tracking=True
    )

    interest_rate = fields.Float(
        string='Interest Rate (%)', tracking=True,
        compute='_compute_interest_rate', store=True, readonly=True,
        help='Flat interest rate, percent of principal, from Loan Type.')

    installment_count = fields.Integer(
        string='Number of Installments', required=True, default=12,
        tracking=True,
        help='Number of monthly installments the repayment is spread over.')

    start_date = fields.Date(
        string='First Installment Date', required=True,
        default=fields.Date.context_today, tracking=True,
        help='Due date of the first repayment installment '
             '(applied from the disburse date).')

    reason = fields.Text(string='Reason / Purpose')

    repayment_line_ids = fields.One2many(
        'st.hr.loan.line', 'loan_id', string='Repayment Schedule')

    total_repayable = fields.Float(
        string='Total Repayable', compute='_compute_totals', store=True,
        help='Principal plus interest.')
    total_paid = fields.Float(
        string='Total Paid', compute='_compute_totals', store=True)
    balance = fields.Float(
        string='Balance', compute='_compute_totals', store=True)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    document_ids = fields.One2many(
        'st.hr.loan.document', 'loan_id', string='Documents')

    is_salary_advance = fields.Boolean(
        related='loan_type_id.is_salary_advance',
        store=True, readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('disbursed', 'Disbursed'),
        ('repaying', 'Repaying'),
        ('repaid', 'Repaid'),
        ('closed', 'Closed'),
        ('refused', 'Refused'),
    ], string='Status', default='draft', tracking=True, copy=False, index=True)

    _sql_constraints = [
        ('check_loan_amount',
         'CHECK (loan_amount >= 0)',
         'Loan amount must be non-negative.'),
        ('check_installment_count',
         'CHECK (installment_count > 0)',
         'Number of installments must be greater than zero.'),
    ]

    @api.depends('loan_amount', 'interest_rate',
                  'repayment_line_ids.amount', 'repayment_line_ids.paid')
    def _compute_totals(self):
        for rec in self:
            rec.total_repayable = (rec.loan_amount or 0.0) * (
                1.0 + (rec.interest_rate or 0.0) / 100.0)
            rec.total_paid = sum(
                line.amount for line in rec.repayment_line_ids if line.paid)
            rec.balance = rec.total_repayable - rec.total_paid

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'st.hr.loan') or 'New'
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            if record.loan_type_id and 'document_ids' not in vals:
                record._sync_required_documents()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'loan_type_id' in vals:
            self._sync_required_documents()
        return res

    def _sync_required_documents(self):
        """Sync document lines for saved loans when loan type changes."""
        Document = self.env['st.hr.loan.document']
        for loan in self:
            if not loan.loan_type_id:
                loan.document_ids.filtered(
                    lambda d: not d.attachment_ids
                ).unlink()
                continue

            required = loan.loan_type_id.required_document_ids
            required_ids = set(required.ids)
            existing = {
                doc.document_type_id.id: doc
                for doc in loan.document_ids
                if doc.document_type_id
            }

            for req in required:
                doc = existing.get(req.id)
                if doc:
                    doc.name = req.name
                else:
                    Document.create({
                        'loan_id': loan.id,
                        'document_type_id': req.id,
                        'name': req.name,
                    })

            loan.document_ids.filtered(
                lambda d: d.document_type_id
                and d.document_type_id.id not in required_ids
                and not d.attachment_ids
            ).unlink()


    @api.depends('loan_type_id')
    def _compute_interest_rate(self):
        for rec in self:
            rec.interest_rate = rec.loan_type_id.interest_rate or 0.0


    @api.onchange('loan_type_id')
    def _onchange_loan_type_id(self):
        """Populate required document lines for new unsaved loans."""
        if self.loan_type_id and self.loan_type_id.is_salary_advance:
            self.installment_count = 1

        if not self.loan_type_id:
            if not self.document_ids:
                return
            if any(doc.attachment_ids for doc in self.document_ids):
                return
            self.document_ids = [(5, 0, 0)]
            return

        if self.document_ids:
            if any(doc.attachment_ids for doc in self.document_ids):
                return
            self.document_ids = [(5, 0, 0)]

        for req in self.loan_type_id.required_document_ids:
            self.document_ids = [(0, 0, {
                'document_type_id': req.id,
                'name': req.name,
            })]


    # def action_submit(self):
    #     for rec in self:
    #
    #         if rec.state != 'draft':
    #             raise UserError('Only draft loans can be submitted.')
    #
    #
    #         if rec.loan_amount <= 0:
    #             label = 'Salary Advance amount' if rec.is_salary_advance else 'Loan amount'
    #             raise UserError('%s must be greater than zero.' % label)
    #
    #         if rec.is_salary_advance and rec.installment_count != 1:
    #             raise UserError(
    #                 'Salary Advance is a one-time settlement. '
    #                 'Number of Installments must be 1.')
    #
    #         if rec.loan_type_id and rec.loan_type_id.max_amount \
    #                 and rec.loan_amount > rec.loan_type_id.max_amount:
    #             raise UserError(
    #                 'Loan amount (%.2f) exceeds the maximum allowed (%.2f) '
    #                 'for loan type "%s".' % (
    #                     rec.loan_amount, rec.loan_type_id.max_amount,
    #                     rec.loan_type_id.name))
    #
    #
    #         if not rec.is_salary_advance:
    #
    #             joining_date = rec.employee_id.contract_id.date_start
    #             if not joining_date:
    #                 raise UserError(
    #                     'Employee "%s" has no joining date set.'
    #                     % rec.employee_id.name)
    #             if relativedelta(date.today(), joining_date).years < 1:
    #                 raise UserError(
    #                     'Employee "%s" must complete 1 year of service '
    #                     'before applying for a loan (joined: %s).'
    #                     % (rec.employee_id.name, joining_date))
    #
    #
    #             if rec.loan_type_id and not rec.is_salary_advance:
    #                 required = rec.loan_type_id.required_document_ids.filtered('is_mandatory')
    #                 for req in required:
    #                     uploaded = rec.document_ids.filtered(
    #                         lambda d, r=req:
    #                         d.document_type_id.id == r.id and d.attachment_ids)
    #                     if not uploaded:
    #                         raise UserError(
    #                             'Please upload the required document: "%s" before submitting.'
    #                             % req.name)
    #     self.write({'state': 'submitted'})

    def action_submit(self):
        for rec in self:

            if rec.state != 'draft':
                raise UserError('Only draft loans can be submitted.')

            if rec.loan_amount <= 0:
                label = 'Salary Advance amount' if rec.is_salary_advance else 'Loan amount'
                raise UserError('%s must be greater than zero.' % label)

            if rec.is_salary_advance and rec.installment_count != 1:
                raise UserError(
                    'Salary Advance is a one-time settlement. '
                    'Number of Installments must be 1.'
                )

            if rec.loan_type_id and rec.loan_type_id.max_amount \
                    and rec.loan_amount > rec.loan_type_id.max_amount:
                raise UserError(
                    'Loan amount (%.2f) exceeds the maximum allowed (%.2f) '
                    'for loan type "%s".' % (
                        rec.loan_amount,
                        rec.loan_type_id.max_amount,
                        rec.loan_type_id.name
                    )
                )

            # Mandatory document validation for Loans only
            if rec.loan_type_id and not rec.is_salary_advance:
                required = rec.loan_type_id.required_document_ids.filtered(
                    'is_mandatory'
                )

                for req in required:
                    uploaded = rec.document_ids.filtered(
                        lambda d, r=req:
                        d.document_type_id.id == r.id
                        and d.attachment_ids
                    )

                    if not uploaded:
                        raise UserError(
                            'Please upload the required document: "%s" before submitting.'
                            % req.name
                        )

        self.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError('Only submitted loans can be approved.')
        self.write({'state': 'approved'})

    def action_refuse(self):
        for rec in self:
            if rec.state not in ('submitted', 'approved'):
                raise UserError(
                    'Only submitted or approved loans can be refused.')
        self.write({'state': 'refused'})

    def action_disburse(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError('Only approved loans can be disbursed.')
            rec._generate_schedule()
        self.write({'state': 'disbursed'})

    def action_close(self):
        for rec in self:
            if rec.state != 'repaid':
                raise UserError('Only repaid loans can be closed.')
            if rec.repayment_line_ids and any(
                    not line.paid for line in rec.repayment_line_ids):
                raise UserError(
                    'Cannot close this loan: one or more repayment '
                    'installments are still unpaid. Balance: %.2f'
                    % rec.balance)
        self.write({'state': 'closed'})

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'refused':
                raise UserError('Only refused loans can be reset to draft.')
        self.write({'state': 'draft'})


    # Repayment schedule

    def _generate_schedule(self):
        """Create repayment installment lines. Called on Disburse."""
        for loan in self:
            loan.repayment_line_ids.unlink()
            count = loan.installment_count or 1
            per_installment = (loan.total_repayable or 0.0) / count
            start = loan.start_date or fields.Date.context_today(loan)
            lines = [(0, 0, {
                'sequence': i + 1,
                'due_date': start + relativedelta(months=i+1),
                'amount': per_installment,
            }) for i in range(count)]
            loan.repayment_line_ids = lines

    def _update_repayment_state(self):
        for loan in self:
            paid_lines = loan.repayment_line_ids.filtered('paid')

            if not paid_lines:
                loan.state = 'disbursed'

            elif len(paid_lines) == len(loan.repayment_line_ids):
                loan.state = 'repaid'

            else:
                loan.state = 'repaying'


class StHrLoanLine(models.Model):
    _name = 'st.hr.loan.line'
    _description = 'Loan Repayment Installment'
    _order = 'sequence, due_date, id'

    loan_id = fields.Many2one('st.hr.loan', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='#', default=10)
    due_date = fields.Date(string='Due Date')
    amount = fields.Float(string='Amount')
    paid = fields.Boolean(string='Paid', default=False)
    currency_id = fields.Many2one(related='loan_id.currency_id', readonly=True)

    def action_mark_paid(self):
        self.paid = True
        self.loan_id._update_repayment_state()

    def action_mark_unpaid(self):
        self.paid = False
        self.loan_id._update_repayment_state()
