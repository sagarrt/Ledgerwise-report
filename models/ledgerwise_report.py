# -*- coding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
##############################################################################

from openerp import fields, models ,api, _
from datetime import datetime,date
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.translate import _
from openerp.exceptions import UserError, ValidationError
import logging
from urlparse import urljoin
from urllib import urlencode
import openerp.addons.decimal_precision as dp
_logger = logging.getLogger(__name__)

class LedgerwiseReport(models.TransientModel):
    '''temporary Main table for ledgerwise details report'''
    _name = "ledgerwise.report"
    _order = 'id asc'
    
    name= fields.Char(string='Name', default='LedgerWise Report')
    ledgerwise_line = fields.One2many('ledgerwise.report.line','order_id','Ledger Details')
    ledgerwise_detailed_line = fields.One2many('ledgerwise.report.line','line_id','Ledger Details')
    report_type = fields.Selection([('detail','Detailed'),('summary','Summary')],'Report Type')
    ledger_type = fields.Selection([('customer','Customer'),('supplier','Supplier')],'Ledger Type')
    partner_id = fields.Many2one('res.partner','Ledger')
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    
    @api.onchange('report_type','ledger_type','partner_id','from_date','to_date')
    def report_type_onchange(self):
    	if self.report_type=='detail':
    		self.ledgerwise_detailed_line.unlink()
	if self.report_type=='summary':
		self.ledgerwise_line.unlink()
	if self.ledger_type or self.partner_id or self.from_date or self.to_date:
		if self.ledgerwise_detailed_line:
			self.ledgerwise_detailed_line.unlink()
		if self.ledgerwise_line:
			self.ledgerwise_line.unlink()
	
    @api.multi
    def search_report(self):
    	domain=[]
    	for res in self:
    		account_move=self.env['account.move.line']
    		if res.from_date:
    			 from_date =res.from_date
		else:
			 res.from_date='2016-07-01'
			 from_date = '2016-07-01'
			 
		if res.to_date:
    			 domain.append(('date','<=',res.to_date))
		else:
			 res.to_date = date.today()
			 domain.append(('date','<=',datetime.strftime(datetime.now(),'%Y-%m-%d')))
			 
    		if res.report_type=='detail':
    			res.ledgerwise_detailed_line.unlink()
    			if not res.partner_id:
    				raise UserError("No Ledger selected")
			partner=('partner_id','=',res.partner_id.id)
			print "----",domain
			# code to find openig balance of customre>>
			opeing_records=account_move.search([partner,('date','<',from_date),('account_id.user_type_id.type','in',('receivable','payable'))],order='date asc')
			opening_balance={}
			if opeing_records:
				for line in opeing_records:
					if opening_balance.get(res.partner_id.id):
						values=opening_balance.get(res.partner_id.id)
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							value -= line.credit
						elif line.debit:
							value += line.debit
						opening_balance.update({res.partner_id.id:values})
					else:
						values=0.0
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							value = -line.credit
						elif line.debit:
							value = line.debit
						opening_balance.update({res.partner_id.id:value})
			opening_bal=opening_balance.get(res.partner_id.id) if opening_balance.get(res.partner_id.id) else 0.0
			self.env['ledgerwise.report.line'].create({'narration':'OPENING BALANCE',
								'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
								'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
								'line_id':res.id})	
			#<<<<
			domain.extend([partner,('date','>=',from_date),('account_id.user_type_id.type','in',('receivable','payable'))])
			# code to find transaction records >>>
			line_ids=self.env['account.move.line'].search(domain,order='date asc')
			for records in line_ids:
				if records.credit and records.account_id.user_type_id.type in ('receivable','payable'):
					opening_bal -= records.credit
					self.env['ledgerwise.report.line'].create({'date':records.date,
							'account':records.account_id.id,
							'journal':records.journal_id.id,
							'narration':records.name if len(records.name)>2 else records.move_id.name,
							'credit_amount':records.credit if records.credit else 0.0,
							'debit_amount':records.debit if records.debit else 0.0,
							'amount':opening_bal,
							'move':records.move_id.id,
							'line_id':res.id})
				if records.debit:
					opening_bal += records.debit
					self.env['ledgerwise.report.line'].create({'date':records.date,
							'account':records.account_id.id,
							'journal':records.journal_id.id,
							'narration':records.name if len(records.name)>2 else records.move_id.name,
							'credit_amount':records.credit if records.credit else 0.0,
							'debit_amount':records.debit if records.debit else 0.0,
							'amount':opening_bal,
							'move':records.move_id.id,
							'line_id':res.id})
			# <<<
			#Closig Balance
			self.env['ledgerwise.report.line'].create({'narration':'CLOSING BALANCE',
								'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
								'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
								'line_id':res.id})	

		if res.report_type=='summary':
			res.ledgerwise_line.unlink()
			partner=False
    			if res.ledger_type=='supplier':
    				partner=('partner_id.supplier','=',True)
			elif res.ledger_type=='customer':
    				partner=('partner_id.customer','=',True)
    			else:
    				raise UserError("No Ledger selected")  	
			# Calculate Opening 
			opeing_records=account_move.search([partner,('date','<',from_date),('account_id.user_type_id.type','in',('receivable','other','payable'))],order='date asc')
			opening_balance={}
			if opeing_records:
				for line in opeing_records:
					if opening_balance.get(line.partner_id.id):
						values=opening_balance.get(line.partner_id.id)
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							values[0] += line.credit
						elif line.debit:
							values[1] += line.debit
						opening_balance.update({line.partner_id.id:values})
					else:
						values=[0,0]
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							values[0] = line.credit
						elif line.debit:
							values[1] = line.debit
						opening_balance.update({line.partner_id.id:values})
			#<<<
			#Calculate Closing >>>
			domain.extend([partner,('date','>=',from_date),('account_id.user_type_id.type','in',('receivable','other','payable'))])
			closing_records=account_move.search(domain,order='date asc')
			closing_balance={}

			if closing_records:
				for line in closing_records:
					if closing_balance.get(line.partner_id.id):
						values=closing_balance.get(line.partner_id.id)
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							values[0] += line.credit
						elif line.debit:
							values[1] += line.debit
						closing_balance.update({line.partner_id.id:values})
					else:
						values=[0,0]
						if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
							values[0] = line.credit
						elif line.debit:
							values[1] = line.debit
						closing_balance.update({line.partner_id.id:values})

			for rec in opening_balance:
				opening = opening_balance.get(rec)[1] - opening_balance.get(rec)[0]
				closing = 0.0
				if closing_balance.get(rec):
					closing_bal = closing_balance.get(rec)[1] - closing_balance.get(rec)[0]
					closing_balance.pop(rec)
					if opening != 0.0:
						closing += closing_bal 
					else:
						closing = closing_bal 
				self.env['ledgerwise.report.line'].create({'partner_id':rec,'credit_amount':opening,
									'debit_amount':closing,'order_id':res.id})

			if closing_balance:
				for rec1 in closing_balance:
					cl_credit = closing_balance.get(rec1)[0]
					cl_debit = closing_balance.get(rec1)[1]
					self.env['ledgerwise.report.line'].create({
									'partner_id':rec1,'credit_amount':0.0,
									'debit_amount':cl_debit - cl_credit,
									'order_id':res.id})

    @api.multi
    def print_report(self):
    	self.ensure_one()
        self.sent = True
        if self.report_type=='detail':
        	return self.env['report'].get_action(self, 'Ledgerwise-report.report_ledgerwiser_report_detailed')
        elif self.report_type=='summary':
        	return self.env['report'].get_action(self, 'Ledgerwise-report.report_ledgerwise_summary')
    	pass
    			 								
class ledgerwiseLine(models.TransientModel):
    '''ledgerwise report line'''
    _name = "ledgerwise.report.line"
	
    order_id = fields.Many2one('ledgerwise.report')
    line_id = fields.Many2one('ledgerwise.report')
    partner_id = fields.Many2one('res.partner','Ledger')
    account = fields.Many2one('account.account','Account')
    journal = fields.Many2one('account.journal','Journal')
    move = fields.Many2one('account.move','Journal Entry')
    narration = fields.Char('Naration')
    date = fields.Date('Date')
    reconcile = fields.Date('Reconcile')
    credit_amount = fields.Float('Credit Amount')
    debit_amount = fields.Float('Debit Amount')
    amount = fields.Float('Balance')
    
    
class res_partner(models.Model):
	_inherit='res.partner'
	
	@api.model
    	def name_search(self, name, args=None, operator='ilike',limit=100):
    		# inherite method to get filter data by context value
    		if self._context.get('ledger') :
    			if not self._context.get('ledger_type'):
    				return []
			elif self._context.get('ledger_type'):
				args=[]
				if self._context.get('ledger_type')=='customer':
					args=[('customer','=',True),('company_type','=','company')]
				if self._context.get('ledger_type')=='supplier':
					args=[('supplier','=',True),('company_type','=','company')]
        	return super(res_partner,self).name_search(name, args, operator=operator,limit=limit)
        		
        		
