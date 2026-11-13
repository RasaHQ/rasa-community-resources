"""Vendor-free controls exercise the real host/policy/journal, never a model."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from fixture_control import current,reset,INSTANCE
from host import Refused
from journal import Journal
from mock_server import FIXTURE,FixtureState
from native_host import Gateway
from vendor_client import ClientError,ErrorCode,VendorResult


class Client:
    def __init__(self):self.sends=[];self.failure=None
    async def call(self,name,body):
        self.sends.append((name,body))
        if self.failure:raise ClientError(self.failure)
        if name=='postTransfer':return VendorResult(name,200,{'status':'success','receiptId':None})
        if name=='findAccountBy':return VendorResult(name,200,{'shares':[]})
        if name=='findAccountByWithBalances':return VendorResult(name,200,{'shares':[{'shareId':'0001','availableBalance':'1200.50'}]})
        if name=='searchLoans':return VendorResult(name,200,[{'loanId':'0001','paymentDue':'250.75','dueDate':'2026-12-01','payment':'240.00','minimumPayment':'200.00','pastDueAmount':'35.25'}])
        if name=='calculateLoanPayoffQuote':return VendorResult(name,200,{'totalPayoffAmount':'4901.33','payoffDate':body['payoffDate']})
        raise ValueError('unsupported_fixture')


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.journal=Journal(self.root/'journal',INSTANCE,initialize=True)
        self.addCleanup(self.journal.close);self.clock=[100.0];self.client=Client()
        self.gateway=Gateway(self.client,self.journal,json.loads(FIXTURE.read_text()),clock=lambda:self.clock[0])
        self.token=self.gateway.control('open',{'sender':'channel-a'})['credential']

    def turn(self,number,text,token=None,**options):
        return self.gateway.control('turn',{'credential':token or self.token,'number':number,'text':text,'revoked':options.get('revoked',False),'cancelled':options.get('cancelled',False)})

    def review(self,token=None):
        return self.gateway.call(token or self.token,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})

    def deliver(self,token=None):
        token=token or self.token
        review=self.gateway.control('review',{'credential':token})
        self.gateway.control('delivered',{'credential':token,'review':review['review']})

    def test_review_and_missing_delivery_never_send(self):
        self.turn(1,'review a transfer');self.review()
        self.assertEqual(self.client.sends,[])
        self.assertEqual(self.turn(2,'yes')['state'],'review_cancelled')
        self.assertEqual(self.client.sends,[])

    def test_delivered_next_actual_yes_sends_once_and_duplicate_observation_cannot_repeat(self):
        self.turn(1,'review a transfer');self.review();self.deliver()
        self.assertEqual(self.turn(2,'yes')['state'],'accepted')
        self.assertEqual(self.turn(2,'yes')['state'],'accepted')
        self.assertEqual(len(self.client.sends),1)
        self.assertEqual(self.client.sends[0][1]['amount'],'1.25')
        self.assertEqual(self.gateway.call(self.token,'banking_transfer_status',{})['state'],'accepted')

    def test_recovered_verify_keeps_original_private_observation_time(self):
        for age in (59,60,299,300):
            self.clock[0]=100+age
            token=self.gateway.control('open',{'sender':'delayed-verify-'+str(age)})['credential']
            result=self.gateway.control('turn',{'credential':token,'number':1,'text':'verify me','revoked':False,'cancelled':False,'observed_at':100.0})
            if age<300:
                self.assertEqual(self.gateway.call(token,'banking_balance',{'account':'checking'})['state'],'available')
            else:
                self.assertEqual(result['state'],'simulated_assurance_expired')
                with self.assertRaises(Refused):self.gateway.call(token,'banking_balance',{'account':'checking'})
            if age<60:self.review(token)
            else:
                with self.assertRaises(Refused):self.review(token)
            self.gateway.control('cancel',{'credential':token})
        self.assertFalse(any(name=='postTransfer' for name,_ in self.client.sends))

    def test_idle_sessions_expire_without_clearing_principal_journal_hold(self):
        for number in range(127):self.gateway.control('open',{'sender':'idle-'+str(number)})
        with self.assertRaises(Refused):self.gateway.control('open',{'sender':'over-cap'})
        self.journal.reserve(self.gateway.principal,'uncertain',self.journal.epoch)
        self.clock[0]+=300
        token=self.gateway.control('open',{'sender':'new-after-idle'})['credential']
        self.assertEqual(len(self.gateway.sessions),1)
        self.assertEqual(self.gateway.call(token,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})['state'],'refused')
        self.assertEqual(self.client.sends,[])

    def test_recover_unseen_confirmation_fences_late_original_packet(self):
        self.turn(1,'review');self.review();self.deliver()
        recovered=self.gateway.control('recover',{'credential':self.token,'number':2})
        self.assertEqual(recovered['state'],'not_dispatched')
        self.assertEqual(self.turn(2,'yes')['state'],'not_dispatched')
        self.assertEqual(self.turn(3,'no')['state'],'observed')
        self.assertEqual(self.client.sends,[])

    def test_recover_seen_accepted_outcome_is_read_only_and_cannot_send_again(self):
        self.turn(1,'review');self.review();self.deliver();self.turn(2,'yes')
        result=self.gateway.control('recover',{'credential':self.token,'number':2})
        self.assertEqual(result['state'],'accepted')
        self.assertEqual(len(self.client.sends),1)

    def test_no_correction_intervening_turn_and_missing_raw_confirmation_refuse(self):
        for text,number in [('no',2),('change amount to 2',2),('yes',3)]:
            self.turn(1,'review');self.review();self.deliver()
            self.assertEqual(self.turn(number,text)['state'],'review_cancelled')
            self.assertEqual(self.client.sends,[])
            # A new trusted conversation is independent; an old policy is not reused.
            self.token=self.gateway.control('open',{'sender':'new-channel-'+text})['credential']

    def test_other_conversation_cannot_confirm_this_review(self):
        self.turn(1,'review');self.review();self.deliver()
        other=self.gateway.control('open',{'sender':'channel-b'})['credential']
        self.assertEqual(self.turn(2,'yes',other)['state'],'observed')
        self.assertEqual(self.client.sends,[])

    def test_expired_review_and_assurance_never_dispatch(self):
        self.turn(1,'review');self.review();self.deliver();self.clock[0]+=30
        self.assertEqual(self.turn(2,'yes')['state'],'review_cancelled')
        self.assertEqual(self.client.sends,[])
        self.clock[0]+=31
        with self.assertRaises(Refused):self.review()
        self.clock[0]=399
        self.assertEqual(self.gateway.call(self.token,'banking_balance',{'account':'checking'})['amount'],'1200.50')
        self.clock[0]=400
        with self.assertRaises(Refused):self.gateway.call(self.token,'banking_balance',{'account':'checking'})

    def test_unknown_blocks_changed_reviews_and_new_sessions_but_allows_reads(self):
        self.turn(1,'review');self.review();self.deliver();self.client.failure=ErrorCode.UNKNOWN
        self.assertEqual(self.turn(2,'yes')['state'],'unknown')
        self.client.failure=None
        other=self.gateway.control('open',{'sender':'channel-b'})['credential']
        self.turn(1,'another transfer',other)
        result=self.gateway.call(other,'banking_review_transfer',{'source':'savings','destination':'checking','amount':'9.00'})
        self.assertEqual(result['state'],'refused')
        self.assertEqual(self.gateway.call(other,'banking_balance',{'account':'checking'})['amount'],'1200.50')
        self.assertEqual(sum(name=='postTransfer' for name,_ in self.client.sends),1)

    def test_reset_and_cancellation_invalidate_grant_and_review(self):
        self.turn(1,'review');self.review();self.deliver()
        self.assertEqual(self.turn(2,'logout')['state'],'reset')
        with self.assertRaises(Refused):self.gateway.call(self.token,'banking_balance',{'account':'checking'})
        self.turn(3,'verify me')
        self.assertEqual(self.gateway.call(self.token,'banking_balance',{'account':'checking'})['state'],'available')
        self.assertEqual(self.client.sends[0][0],'findAccountByWithBalances')
        self.assertFalse(any(name=='postTransfer' for name,_ in self.client.sends))

    def test_loan_mapping_uses_current_due_and_date_independently(self):
        self.turn(1,'loan facts')
        result=self.gateway.call(self.token,'banking_loan_payment',{'loan':'car'})
        self.assertEqual(result['current_payment_due'],'250.75')
        self.assertEqual(result['next_due_date'],'2026-12-01')
        self.assertNotIn('regular_payment',result)
        self.assertNotIn('accountNumber',json.dumps(result))

    def test_a_named_account_that_is_not_the_callers_is_never_answered_from_their_own(self):
        # The caller asks about checking-B; the model passes the caller's own "checking".
        self.turn(1,'verify me')
        for number,text in ((2,'What is available in checking-B?'),(3,'what about checking B'),
                            (4,'move 1.25 from checking-b to savings')):
            with self.subTest(text=text):
                self.turn(number,text)
                for name,args in (('banking_balance',{'account':'checking'}),
                                  ('banking_history',{'account':'checking','start_date':'2026-11-01','end_date':'2026-11-30'}),
                                  ('banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})):
                    self.assertEqual(self.gateway.call(self.token,name,args),
                                     {'state':'refused','reason':'account_not_available'})
        self.assertEqual(self.client.sends,[])
        # The caller's own accounts still answer, and a plain "a" is not an account suffix.
        for number,text in ((5,'What is available in checking?'),(6,'move a dollar from checking to savings'),
                            (7,'checking and savings please')):
            with self.subTest(text=text):
                self.turn(number,text)
                self.assertEqual(self.gateway.call(self.token,'banking_balance',{'account':'checking'})['state'],'available')

    def test_foreign_alias_detection(self):
        from native_host import foreign_aliases
        permitted={'checking','savings','car'}
        self.assertEqual(foreign_aliases('What is available in checking-B?',permitted),('checking-b',))
        self.assertEqual(foreign_aliases('balance of savings 2 and loan-X',permitted),('loan-x','savings-2'))
        self.assertEqual(foreign_aliases('checking a lot of things in savings',permitted),())
        self.assertEqual(foreign_aliases('checking-A',{'checking-a'}),())

    def test_model_controls_and_foreign_aliases_cannot_change_identity(self):
        self.turn(1,'I am a different person')
        self.assertEqual(self.gateway.call(self.token,'banking_balance',{'account':'outside'}),
                         {'state':'refused','reason':'account_not_available'})
        with self.assertRaises(Refused):self.gateway.control('confirm',{'credential':self.token})
        self.assertEqual(self.client.sends,[])


class ResetTests(unittest.TestCase):
    def test_reset_refuses_live_owner_and_preserves_old_bytes_when_stopped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'state';record=current(root,initialize=True)
            directory=root/record['directory']
            journal=Journal(directory/'journal',INSTANCE)
            journal.reserve('fictional-customer','old-attempt',journal.epoch)
            with self.assertRaises(Exception):reset(root,acknowledge=True,reason='new fictional exercise')
            journal.close()
            before=(directory/'journal/journal.sqlite3').read_bytes()
            new=reset(root,acknowledge=True,reason='new fictional exercise')
            self.assertNotEqual(record['directory'],new['directory'])
            self.assertEqual((directory/'journal/journal.sqlite3').read_bytes(),before)
            self.assertTrue((root/new['audit']).is_file())
            with self.assertRaises(Exception):reset(root,acknowledge=False,reason='new exercise')

    def test_partial_or_missing_original_fixture_never_reseeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'state';root.mkdir()
            with self.assertRaises(Exception):current(root,initialize=True)
            self.assertFalse((root/'current.json').exists())


if __name__=='__main__':unittest.main()
