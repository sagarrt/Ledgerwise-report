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
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.
#
##############################################################################
{
    'name': 'Ledgerwise report', 
    'version': '11.0',
    'category': 'Accounting',
    'sequence': 2001,
    'summary': 'Manage to view and print ledgerwise report',
    'description': ''' View Customer and Supplier ledger report, in Detailed and Summary.
                       Shows all customer and vender outstanding opening balance according date.
                       Employee Ledger-report(Payable/Receviable and other).
                       Account Ledger-report in summary and detailed.
                       print all report in PDF format''',
                       
    'author': 'Developer_SRT',
    'website': 'www.test.com',
    'licence':'LGPL-3',
    
    'depends': ['account','product','hr'],
    'data': [
                'views/ledgerwise_report.xml',
                'wizard/report_ledgerwise_detailed.xml',
                'wizard/report_ledgerwise_summary.xml',
                ],
    'demo': [],
    'test': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}


