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

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo import api,fields, models, _
from datetime import datetime,date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError

class LedgerwiseReport(models.Model):
	'''temporary Main table for ledgerwise details report'''
	_name = "ledgerwise.report"
	_order = 'id asc'
    
	name= fields.Char(string='Name', default='LedgerWise Report')
	ledgerwise_line = fields.One2many('ledgerwise.report.line','order_id','Ledger Details')
	ledgerwise_detailed_line = fields.One2many('ledgerwise.report.line','line_id','Ledger Details')
	ledgerwise_account_line  = fields.One2many('ledgerwise.report.line','acc_id','Ledger Details')
	report_type = fields.Selection([('detail','Detailed'),('summary','Summary')],'Report Type')
	ledger_type = fields.Selection([('customer','Customer'),('supplier','Supplier'),
    								('ledger','General Ledger'),('employee','Employees'),
    								('bank_cash','Bank & Cash'),],'Ledger Type')
	pay_type = fields.Selection([('pay_rec','Payable/Receivable'),('payable','Payable'),
    								('receve','Receivable'),('other','Other'),('all','All')],
									default='pay_rec',string='Filter')
	account_id = fields.Many2one('account.account','Account')
	partner_id = fields.Many2one('res.partner','Ledger')
	from_date = fields.Date('From Date')
	to_date = fields.Date('To Date')

	@api.onchange('report_type')
	def report_type_onchange(self):
		self.ledger_type=False
	
	@api.onchange('ledger_type')
	def ledger_type_onchange(self):
		self.partner_id=False
		self.from_date=False
		self.to_date=False
		self.account_id=False
		if self.ledger_type =='bank_cash':
			return {'domain':{'account_id':[('user_type_id.type','=','liquidity')]}}
		elif self.ledger_type =='customer':
			return {'domain':{'partner_id':[('customer','=',True)]}}
		elif self.ledger_type =='supplier':
			return {'domain':{'partner_id':[('supplier','=',True)]}}
		elif self.ledger_type =='employee':
			employee = self.env['hr.employee'].search([('address_home_id','!=',False)])
			return {'domain':{'partner_id':[('id','in',[e.address_home_id.id for e in employee])]}}

	@api.multi
	def find_childs_partner(self,partner_id,all_partner=[]):
		#all_partner=[partner_id.id]
		partners_ids = self.env['res.partner'].search([('parent_id','=',partner_id.id)])
		if not partners_ids:
			return [partner_id.id]
		for child in partners_ids:
			child_partners = self.env['res.partner'].search([('parent_id','=',child.id)])
			all_partner.append(child.id)
			if child_partners:
				all_partner + self.find_childs_partner(child,all_partner)
		return all_partner

	@api.multi
	def search_report(self):
		domain=[('move_id.state','=','posted')]
		for res in self:
			account_move=self.env['account.move.line']
			report_line = self.env['ledgerwise.report.line']
			account_obj=self.env['account.account']
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
			 
		if res.report_type=='detail' and res.ledger_type in ('customer','supplier'):
				res.ledgerwise_detailed_line.unlink()
				if not res.partner_id :
					raise UserError("No Ledger selected")

				partner_ids=self.find_childs_partner(res.partner_id,[res.partner_id.id])
				partner=('partner_id','in',partner_ids)
				# code to find openig balance of customre>>
				opeing_records=account_move.search([partner,('date','<',from_date),('account_id.user_type_id.type','in',('receivable','payable'))],order='date asc')
				opening_balance={}
				opening_bal=0.0
				for line in opeing_records:
					if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
						opening_bal -= line.credit
					elif line.debit:
						opening_bal += line.debit

				report_line.create({'narration':'OPENING BALANCE',
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
						report_line.create({'date':records.date,
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
						report_line.create({'date':records.date,
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
				report_line.create({'narration':'CLOSING BALANCE',
								'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
								'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
								'line_id':res.id})	
		
		elif res.report_type=='detail' and res.ledger_type =='employee':
				res.ledgerwise_detailed_line.unlink()
				if not res.partner_id :
					raise UserError("No Ledger selected")
			
				partner=('partner_id','=',res.partner_id.id)
				# code to find openig balance of Employee>>
				acc_id=[]
				if res.pay_type =='pay_rec':
					acc_id = account_obj.search(['|',('name','=','Employees Advances'),
							('user_type_id.type','in',('receivable','payable'))])
				elif  res.pay_type =='all':
					acc_id = account_obj.search([('user_type_id','!=',False)])
				elif res.pay_type =='payable':
					acc_id = account_obj.search([('user_type_id.type','=','receivable')])
				elif  res.pay_type =='receve':
					acc_id = account_obj.search(['|',('user_type_id.type','=','receivable'),
									('name','=','Employees Advances')])
				elif  res.pay_type =='other':
					acc_id = account_obj.search(['|',('name','!=','Employees Advances'),
							('user_type_id.type','not in',('receivable','payable'))])
				account_dom=('account_id','in',acc_id._ids)
			
				opeing_records=account_move.search([partner,account_dom,('date','<',from_date)],
									order='date asc')
				opening_balance={}
				opening_bal=0.0
				for line in opeing_records:
					if line.credit :
						opening_bal -= line.credit
					elif line.debit:
						opening_bal += line.debit

				report_line.create({'narration':'OPENING BALANCE',
							'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
							'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
							'line_id':res.id})	
				#<<<<
				domain.extend([partner,account_dom,('date','>=',from_date)])

				# code to find transaction records >>>
				line_ids=self.env['account.move.line'].search(domain,order='date asc')
				for records in line_ids:
					if records.credit :
						opening_bal -= records.credit
						report_line.create({'date':records.date,
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
						report_line.create({'date':records.date,
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
				report_line.create({'narration':'CLOSING BALANCE',
								'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
								'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
								'line_id':res.id})	

		elif res.report_type=='detail' and res.ledger_type in ('ledger','bank_cash'):
				res.ledgerwise_detailed_line.unlink()
				if not res.account_id :
					raise UserError("No Ledger selected")
				account=('account_id','=',res.account_id.id)
				# code to find openig balance of customre>>
				opeing_records=account_move.search([account,('date','<',from_date)],order='date asc')
				opening_bal=0.0
			
				for line in opeing_records:
					if line.credit:
						opening_bal -= line.credit
					elif line.debit:
						opening_bal += line.debit
							
				report_line.create({'narration':'OPENING BALANCE',
							'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
							'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
							'line_id':res.id})	
				#<<<<
			
				domain.extend([account,('date','>=',from_date)])
				# code to find transaction records >>>
				line_ids=account_move.search(domain,order='date asc')
				for records in line_ids:
					if records.credit:
						opening_bal -= records.credit
						report_line.create({'date':records.date,
							'line_id':res.id,
							'account':records.account_id.id,
							'journal':records.journal_id.id,
							'narration':records.name if len(records.name)>2 \
											else records.move_id.name,
							'credit_amount':records.credit if records.credit else 0.0,
							'debit_amount':records.debit if records.debit else 0.0,
							'move':records.move_id.id,
							'amount':opening_bal,
							'partner_id':records.partner_id.id})
					
					if records.debit :
						opening_bal += records.debit
						report_line.create({'date':records.date,
							'line_id':res.id,
							'account':records.account_id.id,
							'journal':records.journal_id.id,
							'narration':records.name if len(records.name)>2 \
											else records.move_id.name,
							'credit_amount':records.credit if records.credit else 0.0,
							'debit_amount':records.debit if records.debit else 0.0,
							'move':records.move_id.id,
							'amount':opening_bal,
							'partner_id':records.partner_id.id})
							
				#Closig Balance
				report_line.create({'narration':'CLOSING BALANCE',
							'credit_amount':abs(opening_bal) if opening_bal<0.0 else 0.0,
							'debit_amount':opening_bal if opening_bal>0.0 else 0.0,
							'line_id':res.id})

		elif res.report_type=='summary' and res.ledger_type in ('customer','supplier'):
			res.ledgerwise_line.unlink()
			partner=[]
			if res.ledger_type=='supplier':
				partner=[('partner_id.supplier','=',True)]
			elif res.ledger_type=='customer':
				partner=[('partner_id.customer','=',True)]
	
			# Calculate Opening 
			opeing_records=account_move.search(partner+[('date','<',from_date),('account_id.user_type_id.type','in',('receivable','other','payable'))],order='date asc')
			opening_balance={}
			for line in opeing_records:
				if opening_balance.get(line.partner_id.id):
					if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
						opening_balance[line.partner_id.id][0] += line.credit
					elif line.debit:
						opening_balance[line.partner_id.id][1] += line.debit
				else:
					values=[0,0]
					if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
						values[0] = line.credit
					elif line.debit:
						values[1] = line.debit
					opening_balance[line.partner_id.id]=values
			#<<<
			#Calculate Closing >>>
			domain.extend([partner,('date','>=',from_date),('account_id.user_type_id.type','in',('receivable','other','payable'))])
			closing_records=account_move.search(domain,order='date asc')
			closing_balance={}

			domain.extend(partner+[('date','>=',from_date),('account_id.user_type_id.type','in',('receivable','other','payable'))])
			closing_records = account_move.search(domain,order='date asc')
			closing_balance = {}

			for line in closing_records:
				if closing_balance.get(line.partner_id.id):
					if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
						closing_balance[line.partner_id.id][0] += line.credit
					elif line.debit:
						closing_balance[line.partner_id.id][1] += line.debit
				else:
					values=[0,0]
					if line.credit and line.account_id.user_type_id.type in ('receivable','payable'):
						values[0] = line.credit
					elif line.debit:
						values[1] = line.debit
					closing_balance[line.partner_id.id]=values

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
				report_line.create({'partner_id':rec,'credit_amount':opening,
							'debit_amount':closing,'acc_id':res.id})

			if closing_balance:
				for rec1 in closing_balance:
					cl_credit = closing_balance.get(rec1)[0]
					cl_debit = closing_balance.get(rec1)[1]
					report_line.create({'partner_id':rec1,'credit_amount':0.0,
								'debit_amount':cl_debit - cl_credit,
								'acc_id':res.id})
		
		elif res.report_type=='summary' and res.ledger_type =='employee':
			res.ledgerwise_line.unlink()
			res.ledgerwise_account_line.unlink()
			partner=[]
			if res.ledger_type=='employee':
				partner=[('partner_id.customer','=',False),('partner_id.supplier','=',False)]

			domain.extend(partner+[('date','>=',from_date)])
			if res.pay_type =='pay_rec':
				domain.extend(('|',('account_id.user_type_id.type','in',('receivable','payable')),
						('account_id.user_type_id.name','=','Current Assets')))
			elif  res.pay_type =='all':
				filter_type=('account_id.user_type_id.type','in',('receivable','payable','other'))
			elif res.pay_type =='payable':
				filter_type=('account_id.user_type_id.type','=','payable')
			elif  res.pay_type =='receve':
				filter_type=('|',('account_id.user_type_id.type','=','receivable'),
						('account_id.name','=','Current Assets'))
			elif  res.pay_type =='other':
				filter_type=('account_id.user_type_id.type','not in',('receivable','payable'))
	
			closing_records = account_move.search(domain,order='date asc')
			closing_balance = {}

			for line in closing_records:
				if closing_balance.get(line.partner_id.id):
					if line.credit :
						closing_balance[line.partner_id.id][0] += line.credit
					elif line.debit:
						closing_balance[line.partner_id.id][1] += line.debit
				else:
					values=[0,0]
					if line.credit :
						values[0] = line.credit
					elif line.debit:
						values[1] = line.debit
					closing_balance[line.partner_id.id]=values
			
			if closing_balance:
				for rec1 in closing_balance:
					cl_credit = closing_balance.get(rec1)[0]
					cl_debit = closing_balance.get(rec1)[1]
					report_line.create({'partner_id':rec1,'credit_amount':0.0,
								'debit_amount':cl_debit - cl_credit,
								'order_id':res.id})
								
		elif res.report_type=='summary'  and res.ledger_type in ('ledger','bank_cash'):
			res.ledgerwise_account_line.unlink()
			res.ledgerwise_line.unlink()
			domain= [('user_type_id.type','=','liquidity')] if res.ledger_type=='bank_cash' else []
			acc_ids = self.env['account.account'].search(domain)
			account=('account_id','in',acc_ids._ids)

			# Calculate Opening 
			opeing_records=account_move.search([account,('date','<',from_date)],order='date asc')
			opening_balance={}
			for line in opeing_records:
				if opening_balance.get(line.account_id.id):
					if line.credit :
						opening_balance[line.account_id.id][0] += line.credit
					elif line.debit:
						opening_balance[line.account_id.id][1] += line.debit
				else:
					values=[0,0]
					if line.credit:
						values[0] = line.credit
					elif line.debit:
						values[1] = line.debit
					opening_balance[line.account_id.id]=values
			#<<<
			#Calculate Closing >>>

			domain.extend([account,('date','>=',from_date)])
			closing_records = account_move.search(domain,order='date asc')
			closing_balance = {}

			for line in closing_records:
				if closing_balance.get(line.account_id.id):
					if line.credit:
						closing_balance[line.account_id.id][0] += line.credit
					elif line.debit:
						closing_balance[line.account_id.id][1] += line.debit
				else:
					values=[0,0]
					if line.credit:
						values[0] = line.credit
					elif line.debit:
						values[1] = line.debit
					closing_balance[line.account_id.id]=values

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
				report_line.create({'account':rec,'credit_amount':opening,
							'debit_amount':closing,'acc_id':res.id})

			if closing_balance:
				for rec1 in closing_balance:
					cl_credit = closing_balance.get(rec1)[0]
					cl_debit = closing_balance.get(rec1)[1]
					report_line.create({'account':rec1,'credit_amount':0.0,
								'debit_amount':cl_debit - cl_credit,
								'acc_id':res.id})

	@api.multi
	def print_report(self):
		self.ensure_one()
		self.sent = True
		self.search_report()
		if self.report_type=='detail':
			return self.env['report'].get_action(self, 'Ledgerwise-report.report_ledgerwiser_report_detailed')
		elif self.report_type=='summary':
			return self.env['report'].get_action(self, 'Ledgerwise-report.report_ledgerwise_summary')
    			 								
class ledgerwiseLine(models.Model):
    '''ledgerwise report line'''
    _name = "ledgerwise.report.line"
	
    order_id = fields.Many2one('ledgerwise.report')
    line_id = fields.Many2one('ledgerwise.report')
    acc_id = fields.Many2one('ledgerwise.report')
    partner_id = fields.Many2one('res.partner','Ledger')
    account = fields.Many2one('account.account','Account')
    journal = fields.Many2one('account.journal','Journal')
    move = fields.Many2one('account.move','Journal Entry')
    narration = fields.Char('Naration')
    date = fields.Date('Date')
    credit_amount = fields.Float('Credit Amount')
    debit_amount = fields.Float('Debit Amount')
    amount = fields.Float('Balance')
    
