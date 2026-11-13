# SPDX-License-Identifier: MIT
"""The SOAP bodies this example produces, recorded on the pinned archive.

Each entry is (operation, "request" or "response", body XML): every request
body silverlake_demo/client.py sends and every success reply the mock builds,
from one run of the client against silverlake_demo/mock.SilverLakeMock on the
pinned archive (accounts, balance, both history pages, loan payment, a payoff
with a quote and one without, one transfer). Recorded before the client was
moved onto the generated models, so it is also the reference the model-built
requests are compared with. All data is fictional. Regenerate only together
with new pins.
"""

EXCHANGES = [('AcctSrch',
  'request',
  '<ns0:AcctSrch '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:MaxRec>20</ns0:MaxRec></ns0:SrchMsgRqHdr><ns0:CustId>C100001</ns0:CustId></ns0:AcctSrch>'),
 ('AcctSrch',
  'response',
  '<ns0:AcctSrchResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:SentRec>3</ns0:SentRec><ns0:MoreRec>false</ns0:MoreRec></ns0:SrchMsgRsHdr><ns0:AcctSrchRecArray><ns0:AcctSrchRec><ns0:AccountId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:AccountId><ns0:CustId>C100001</ns0:CustId><ns0:ProdDesc>Fictional '
  'Checking</ns0:ProdDesc></ns0:AcctSrchRec><ns0:AcctSrchRec><ns0:AccountId><ns0:AcctId>1001002</ns0:AcctId><ns0:AcctType>S</ns0:AcctType></ns0:AccountId><ns0:CustId>C100001</ns0:CustId><ns0:ProdDesc>Fictional '
  'Savings</ns0:ProdDesc></ns0:AcctSrchRec><ns0:AcctSrchRec><ns0:AccountId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:AccountId><ns0:CustId>C100001</ns0:CustId><ns0:ProdDesc>Fictional '
  'Auto Loan</ns0:ProdDesc></ns0:AcctSrchRec></ns0:AcctSrchRecArray></ns0:AcctSrchResponse>'),
 ('AcctBalInq',
  'request',
  '<ns0:AcctBalInq '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRqHdr><ns0:InAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:InAcctId></ns0:AcctBalInq>'),
 ('AcctBalInq',
  'response',
  '<ns0:AcctBalInqResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRsHdr><ns0:InAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:InAcctId><ns0:CurBal>1275.00</ns0:CurBal><ns0:AvlBal>1250.00</ns0:AvlBal></ns0:AcctBalInqResponse>'),
 ('AcctHistSrch',
  'request',
  '<ns0:AcctHistSrch '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:MaxRec>3</ns0:MaxRec></ns0:SrchMsgRqHdr><ns0:InAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:InAcctId></ns0:AcctHistSrch>'),
 ('AcctHistSrch',
  'response',
  '<ns0:AcctHistSrchResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:SentRec>3</ns0:SentRec><ns0:MoreRec>true</ns0:MoreRec><ns0:Cursor>3</ns0:Cursor></ns0:SrchMsgRsHdr><ns0:AcctHistSrchRecArray><ns0:AcctHistSrchRec><ns0:DepHistSrchRec><ns0:DepAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:DepAcctId><ns0:TrnCodeCode>200</ns0:TrnCodeCode><ns0:TrnCodeDesc>Fictional '
  'Market</ns0:TrnCodeDesc><ns0:PostDt>2026-11-04</ns0:PostDt><ns0:Amt>42.00</ns0:Amt><ns0:TrnType>Debit</ns0:TrnType><ns0:AffCode>0</ns0:AffCode></ns0:DepHistSrchRec></ns0:AcctHistSrchRec><ns0:AcctHistSrchRec><ns0:DepHistSrchRec><ns0:DepAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:DepAcctId><ns0:TrnCodeCode>100</ns0:TrnCodeCode><ns0:TrnCodeDesc>Fictional '
  'Payroll</ns0:TrnCodeDesc><ns0:PostDt>2026-11-03</ns0:PostDt><ns0:Amt>900.00</ns0:Amt><ns0:TrnType>Credit</ns0:TrnType><ns0:AffCode>0</ns0:AffCode></ns0:DepHistSrchRec></ns0:AcctHistSrchRec><ns0:AcctHistSrchRec><ns0:DepHistSrchRec><ns0:DepAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:DepAcctId><ns0:TrnCodeCode>200</ns0:TrnCodeCode><ns0:TrnCodeDesc>Fictional '
  'Pharmacy</ns0:TrnCodeDesc><ns0:PostDt>2026-11-01</ns0:PostDt><ns0:Amt>15.50</ns0:Amt><ns0:TrnType>Debit</ns0:TrnType><ns0:AffCode>0</ns0:AffCode></ns0:DepHistSrchRec></ns0:AcctHistSrchRec></ns0:AcctHistSrchRecArray></ns0:AcctHistSrchResponse>'),
 ('AcctHistSrch',
  'request',
  '<ns0:AcctHistSrch '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:MaxRec>3</ns0:MaxRec><ns0:Cursor>3</ns0:Cursor></ns0:SrchMsgRqHdr><ns0:InAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:InAcctId></ns0:AcctHistSrch>'),
 ('AcctHistSrch',
  'response',
  '<ns0:AcctHistSrchResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:SrchMsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr><ns0:SentRec>2</ns0:SentRec><ns0:MoreRec>false</ns0:MoreRec></ns0:SrchMsgRsHdr><ns0:AcctHistSrchRecArray><ns0:AcctHistSrchRec><ns0:DepHistSrchRec><ns0:DepAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:DepAcctId><ns0:TrnCodeCode>200</ns0:TrnCodeCode><ns0:TrnCodeDesc>Fictional '
  'Gas '
  'Co</ns0:TrnCodeDesc><ns0:PostDt>2026-10-29</ns0:PostDt><ns0:Amt>80.00</ns0:Amt><ns0:TrnType>Debit</ns0:TrnType><ns0:AffCode>0</ns0:AffCode></ns0:DepHistSrchRec></ns0:AcctHistSrchRec><ns0:AcctHistSrchRec><ns0:DepHistSrchRec><ns0:DepAcctId><ns0:AcctId>1001001</ns0:AcctId><ns0:AcctType>D</ns0:AcctType></ns0:DepAcctId><ns0:TrnCodeCode>100</ns0:TrnCodeCode><ns0:TrnCodeDesc>Fictional '
  'Refund</ns0:TrnCodeDesc><ns0:PostDt>2026-10-27</ns0:PostDt><ns0:Amt>25.00</ns0:Amt><ns0:TrnType>Credit</ns0:TrnType><ns0:AffCode>0</ns0:AffCode></ns0:DepHistSrchRec></ns0:AcctHistSrchRec></ns0:AcctHistSrchRecArray></ns0:AcctHistSrchResponse>'),
 ('AcctInq',
  'request',
  '<ns0:AcctInq '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRqHdr><ns0:InAcctId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:InAcctId></ns0:AcctInq>'),
 ('AcctInq',
  'response',
  '<ns0:AcctInqResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRsHdr><ns0:LnAcctInqRec><ns0:x_LnInfoRec><ns0:LnInfoRec><ns0:PmtAmtDue>242.40</ns0:PmtAmtDue><ns0:PmtAmt>182.40</ns0:PmtAmt><ns0:PastDueAmt>60.00</ns0:PastDueAmt><ns0:NxtSchedPmtDt>2026-12-15</ns0:NxtSchedPmtDt><ns0:NxtPayDt>2026-12-01</ns0:NxtPayDt></ns0:LnInfoRec><ns0:LoanAcctId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:LoanAcctId><ns0:PersonName><ns0:ComName>Fictional '
  'Customer</ns0:ComName></ns0:PersonName></ns0:x_LnInfoRec></ns0:LnAcctInqRec></ns0:AcctInqResponse>'),
 ('LnPayoffInq',
  'request',
  '<ns0:LnPayoffInq '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRqHdr><ns0:AccountId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:AccountId><ns0:EffDt>2026-11-20</ns0:EffDt></ns0:LnPayoffInq>'),
 ('LnPayoffInq',
  'response',
  '<ns0:LnPayoffInqResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRsHdr><ns0:AccountId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:AccountId><ns0:EffDt>2026-11-20</ns0:EffDt><ns0:PayoffAmt>4120.55</ns0:PayoffAmt></ns0:LnPayoffInqResponse>'),
 ('LnPayoffInq',
  'request',
  '<ns0:LnPayoffInq '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRqHdr><ns0:AccountId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:AccountId><ns0:EffDt>2026-12-24</ns0:EffDt></ns0:LnPayoffInq>'),
 ('LnPayoffInq',
  'response',
  '<ns0:LnPayoffInqResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRsHdr><ns0:AccountId><ns0:AcctId>7001001</ns0:AcctId><ns0:AcctType>L</ns0:AcctType></ns0:AccountId><ns0:EffDt>2026-12-24</ns0:EffDt></ns0:LnPayoffInqResponse>'),
 ('XferAdd',
  'request',
  '<ns0:XferAdd '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRqHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRqHdr><ns0:AcctIdFrom><ns0:FromAcctId>1001001</ns0:FromAcctId><ns0:FromAcctType>D</ns0:FromAcctType></ns0:AcctIdFrom><ns0:AcctIdTo><ns0:ToAcctId>1001002</ns0:ToAcctId><ns0:ToAcctType>S</ns0:ToAcctType></ns0:AcctIdTo><ns0:XferRec><ns0:Amt>25.00</ns0:Amt></ns0:XferRec></ns0:XferAdd>'),
 ('XferAdd',
  'response',
  '<ns0:XferAddResponse '
  'xmlns:ns0="http://jackhenry.com/jxchange/TPG/2008"><ns0:MsgRsHdr><ns0:jXchangeHdr><ns0:AuditUsrId>rasa-demo</ns0:AuditUsrId><ns0:AuditWsId>rasa-demo</ns0:AuditWsId></ns0:jXchangeHdr></ns0:MsgRsHdr><ns0:XferKey>a26f3703eb684e739e1c</ns0:XferKey><ns0:RsStat>Success</ns0:RsStat></ns0:XferAddResponse>')]
