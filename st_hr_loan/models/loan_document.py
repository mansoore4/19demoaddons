from odoo import api, fields, models


class StHrLoanTypeDocument(models.Model):
    _name = 'st.hr.loan.type.document'
    _description = 'Required Document for Loan Type'

    loan_type_id = fields.Many2one(
        'st.hr.loan.type', required=True, ondelete='cascade')
    name = fields.Char(string='Document Name', required=True)
    is_mandatory = fields.Boolean(string='Mandatory', default=True)


class StHrLoanDocument(models.Model):
    _name = 'st.hr.loan.document'
    _description = 'Loan Document Upload'

    loan_id = fields.Many2one(
        'st.hr.loan', required=True, ondelete='cascade', index=True)
    document_type_id = fields.Many2one(
        'st.hr.loan.type.document', string='Document Required')
    name = fields.Char(string='Name')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'st_hr_loan_document_ir_attachment_rel',
        'document_id',
        'attachment_id',
        string='File',
    )

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        documents._link_attachments()
        return documents

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._link_attachments()
        return res

    def unlink(self):
        attachments = self.attachment_ids
        res = super().unlink()
        attachments.unlink()
        return res

    def _link_attachments(self):
        for document in self:
            document.attachment_ids.write({
                'res_model': 'st.hr.loan.document',
                'res_id': document.id,
            })
