"""Drive actual decorated banking tools with a counted host boundary."""
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from premier_demo import rasa_adapter as adapter
from lib import reply_policy as policy

class ReplyAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context=SimpleNamespace(is_cancelled=False,events=[],send=self.send)
        self.messages=[]
        self.native=SimpleNamespace(sender_id="reply-controls",turn=SimpleNamespace(text="review"),is_cancelled=False)
        self.host=Host()
        self.conversation=adapter._Conversation("http://127.0.0.1:1",self.host,"session")
        adapter._conversations.clear();policy._delivered.clear()
        adapter._conversations[("http://127.0.0.1:1",self.native.sender_id)]=self.conversation
        self.addCleanup(adapter._conversations.clear);self.addCleanup(policy._delivered.clear)
        for target,name,value in [(adapter,"current_turn_context",lambda:self.native),
                                   (policy,"current_turn_context",lambda:self.native)]:
            p=patch.object(target,name,value);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{"PREMIER_HOST_URL":"http://127.0.0.1:1","PREMIER_HOST_CAPABILITY":"c"*40})
        p.start();self.addCleanup(p.stop)
        self.turn("review")

    async def send(self,text):self.messages.append(text)

    def turn(self,text):
        self.native.turn=SimpleNamespace(text=text)
        self.context.events.append(SimpleNamespace(as_dict=lambda:{"event":"user","text":text,"timestamp":time.time()}))

    async def review(self):
        return await adapter.banking_review_transfer("checking-A","bills-A","5.00","USD",context=self.context)

    async def test_repeated_review_in_one_turn_is_delivered_once_and_acceptance_says_not_posted(self):
        await self.review();await self.review()
        self.assertEqual(self.host.reviews,1)
        self.assertEqual(len(self.messages),1)
        self.assertIn("Review: transfer USD 5.00",self.messages[0])
        self.turn("confirm transfer")
        result=await adapter.banking_submit_transfer(context=self.context)
        self.assertEqual(result.llm_response["state"],"accepted")
        self.assertEqual(self.host.sends,1)
        self.assertIn("Accepted does not mean posted",self.messages[-1])

    async def test_intervening_read_cancels_review_and_confirmation_requires_new_request(self):
        await self.review();self.turn("balance")
        await adapter.banking_balance("checking-A",context=self.context)
        self.turn("confirm transfer")
        result=await adapter.banking_submit_transfer(context=self.context)
        self.assertEqual(result.llm_response["state"],"refused")
        self.assertEqual(self.host.sends,0)
        self.assertIn("Request a new transfer",self.messages[-1])
        self.assertNotIn("confirm again",self.messages[-1])

    async def test_unknown_outcome_never_invites_a_new_transfer(self):
        await self.review();self.host.state="unknown";self.turn("confirm transfer")
        await adapter.banking_submit_transfer(context=self.context)
        self.turn("confirm transfer")
        result=await adapter.banking_submit_transfer(context=self.context)
        self.assertEqual(result.llm_response["state"],"unknown")
        self.assertEqual(self.host.sends,1)
        self.assertIn("Do not retry",self.messages[-1])
        self.assertNotIn("Request a new transfer",self.messages[-1])


class Host:
    def __init__(self):self.reviews=0;self.sends=0;self.state="accepted"
    async def call(self,session,name,args):
        if name=="banking_review_transfer":
            self.reviews+=1
            data=dict(state="pending",review="private-review",source="checking-A",destination="bills-A",amount="5.00",currency="USD")
        else:data=dict(state="available",amount="1250.00",currency="USD")
        return SimpleNamespace(isError=False,structuredContent=data)
    def arm(self,*args):pass
    def cancel(self,*args):pass
    def confirm(self,*args):pass
    def submit(self,*args):self.sends+=1;return {"state":self.state}
    def confirm_and_send(self,*args):self.sends+=1;return {"state":self.state}
