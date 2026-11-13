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
        adapter._conversations.clear();policy._delivered.clear();policy._sent.clear()
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

    async def test_no_confirmation_is_accepted_after_an_interrupted_or_declined_review(self):
        # The three sequences from the four-bank walkthroughs. The middle turn calls
        # no tool at all, as a model may answer it in text, so only the raw turn
        # count stands between it and a late acceptance.
        for middle, last in (("What is my balance?", "Confirm transfer."),
                             ("No, do not transfer.", "Confirm transfer."),
                             ("No, do not transfer.", "Yes.")):
            with self.subTest(middle=middle, last=last):
                adapter._conversations.clear(); policy._delivered.clear(); policy._sent.clear()
                self.host = Host()
                self.conversation = adapter._Conversation("http://127.0.0.1:1", self.host, "session")
                adapter._conversations[("http://127.0.0.1:1", self.native.sender_id)] = self.conversation
                self.turn("review"); await self.review()
                self.turn(middle)
                self.turn(last)
                result = await adapter.banking_submit_transfer(context=self.context)
                self.assertNotEqual(result.llm_response["state"], "accepted")
                self.assertEqual(self.host.sends, 0)
                self.assertNotIn("accepted", self.messages[-1].casefold())

    async def test_a_confirmation_never_reads_an_earlier_accepted_transfer_as_this_one(self):
        # Transfer A accepted; review B then cancelled; a raw confirm routed to the
        # status tool must not say accepted, and nothing new is sent.
        await self.review();self.turn("confirm transfer")
        await adapter.banking_submit_transfer(context=self.context)
        self.assertEqual(self.host.sends,1)
        self.turn("review");await self.review()
        self.turn("No, do not transfer.")
        for text in ("Confirm transfer.","Yes."):
            with self.subTest(text=text):
                self.turn(text);policy._delivered.clear();before=len(self.messages)
                result=await adapter.banking_transfer_status(context=self.context)
                self.assertEqual(result.llm_response["state"],"not_submitted")
                self.assertTrue(all("accepted" not in m.casefold() for m in self.messages[before:]))
                self.assertIn("Request a new transfer",self.messages[-1])
        self.assertEqual(self.host.sends,1)
        self.turn("What happened to my earlier transfer?")
        asked=await adapter.banking_transfer_status(context=self.context)
        self.assertEqual(asked.llm_response["state"],"accepted")  # an explicit question still gets it

    async def test_a_confirmation_after_an_unknown_outcome_never_invites_a_new_transfer(self):
        await self.review();self.host.state="unknown";self.turn("confirm transfer")
        await adapter.banking_submit_transfer(context=self.context)
        self.turn("Yes.");policy._delivered.clear()
        result=await adapter.banking_transfer_status(context=self.context)
        self.assertEqual(result.llm_response["state"],"unknown")
        self.assertIn("Do not retry",self.messages[-1])
        self.assertNotIn("Request a new transfer",self.messages[-1])
        self.assertEqual(self.host.sends,1)

    async def test_an_unknown_outcome_held_across_a_restart_is_never_retried(self):
        # After a restart the conversation is new (no last_submit_state), but the
        # host's journal still holds the unknown outcome.
        self.host.sends,self.host.state=1,"unknown"
        self.assertIsNone(self.conversation.last_submit_state)
        for text,tool in (("Confirm transfer.",adapter.banking_submit_transfer),("Yes.",adapter.banking_transfer_status)):
            with self.subTest(text=text):
                self.turn(text);policy._delivered.clear();policy._sent.clear()
                result=await tool(context=self.context)
                self.assertEqual(result.llm_response["state"],"unknown")
                self.assertIn("Do not retry",self.messages[-1])
                self.assertNotIn("Request a new transfer",self.messages[-1])
        self.assertEqual(self.host.sends,1)

    async def test_a_status_that_was_never_learned_is_never_cleared_after_a_restart(self):
        # A failed (MCP isError), stateless or unrecognized status probe is not a
        # resolved outcome: no new-transfer advice and no send, on both routes.
        for label,reply in (("mcp_error",SimpleNamespace(isError=True,structuredContent=None,content=[])),
                            ("no_state",SimpleNamespace(isError=False,structuredContent={})),
                            ("unrecognized",SimpleNamespace(isError=False,structuredContent={"state":"queued"}))):
            for text,tool in (("Confirm transfer.",adapter.banking_submit_transfer),("Yes.",adapter.banking_transfer_status)):
                with self.subTest(label=label,text=text):
                    self.host.status_reply=reply
                    self.assertIsNone(self.conversation.last_submit_state)
                    self.turn(text);policy._delivered.clear();policy._sent.clear()
                    result=await tool(context=self.context)
                    self.assertEqual(result.llm_response["state"],"unknown")
                    self.assertIn("Do not retry",self.messages[-1])
                    self.assertNotIn("Request a new transfer",self.messages[-1])
        self.assertEqual(self.host.sends,0)

    async def test_unknown_outcome_never_invites_a_new_transfer(self):
        await self.review();self.host.state="unknown";self.turn("confirm transfer")
        await adapter.banking_submit_transfer(context=self.context)
        self.turn("confirm transfer")
        result=await adapter.banking_submit_transfer(context=self.context)
        self.assertEqual(result.llm_response["state"],"unknown")
        self.assertEqual(self.host.sends,1)
        self.assertIn("Do not retry",self.messages[-1])
        self.assertNotIn("Request a new transfer",self.messages[-1])


    async def test_verify_me_refreshes_once_and_delivers_the_exact_sentence(self):
        self.turn("Verify me.")
        result=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response,{"state":"verified"})
        self.assertEqual(len(self.host.assured),1)
        self.assertLess(self.host.assured[0],5)
        self.assertEqual(self.messages,[adapter.VERIFIED_TEXT])
        self.assertEqual((self.host.sends,self.host.reviews),(0,0))

    async def test_verify_me_without_a_usable_timestamp_says_nothing_refreshed(self):
        self.native.turn=SimpleNamespace(text="Verify me.")
        self.context.events.append(SimpleNamespace(as_dict=lambda:{"event":"user","text":"Verify me.","timestamp":None}))
        result=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response,{"state":"refused","reason":"verification_not_observed"})
        self.assertEqual((self.host.assured,self.messages),([],[]))

    async def test_a_consumed_verify_phrase_is_not_announced_twice(self):
        self.turn("Verify me.")
        await adapter.banking_refresh_verification(context=self.context)
        again=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(again.llm_response,{"state":"refused","reason":"verification_not_observed"})
        self.assertEqual(len(self.host.assured),1)
        self.assertEqual(self.messages,[adapter.VERIFIED_TEXT])

    async def test_a_stale_verify_phrase_gives_no_success_wording(self):
        self.native.turn=SimpleNamespace(text="Verify me.")
        stamp=time.time()-adapter.FRESH_SECONDS-5
        self.context.events.append(SimpleNamespace(as_dict=lambda:{"event":"user","text":"Verify me.","timestamp":stamp}))
        result=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response,{"state":"refused","reason":"verification_not_observed"})
        self.assertEqual(self.messages,[])

    async def test_a_session_start_pass_never_verifies(self):
        # Rasa first runs the opening message as a SESSION_START turn with the
        # caller's text pending; only the caller's own turn may verify.
        self.turn("Verify me.")
        self.native.turn=SimpleNamespace(text="Verify me.",trigger="session_start")
        result=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response,{"state":"refused","reason":"say_verify_me"})
        self.assertEqual((self.host.assured,self.messages),([],[]))

    async def test_the_same_host_sentence_is_delivered_once_per_turn(self):
        from lib import reply_policy as rp
        self.turn("Verify me.")
        await rp.deliver_reply(self.context, adapter.VERIFIED_TEXT)
        rp._delivered.clear()  # as after the reply hook consumed the delivery record
        await rp.deliver_reply(self.context, adapter.VERIFIED_TEXT)
        self.assertEqual(self.messages, [adapter.VERIFIED_TEXT])

    async def test_verification_tool_does_nothing_without_the_raw_phrase(self):
        self.turn("what is my balance")
        result=await adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response,{"state":"refused","reason":"say_verify_me"})
        self.assertEqual(self.host.assured,[])
        self.assertEqual(self.messages,[])

class Host:
    def __init__(self):self.reviews=0;self.sends=0;self.state="accepted";self.assured=[]
    def assure(self,session,age):self.assured.append(age)
    async def call(self,session,name,args):
        if name=="banking_review_transfer":
            self.reviews+=1
            data=dict(state="pending",review="private-review",source="checking-A",destination="bills-A",amount="5.00",currency="USD")
        elif name=="banking_transfer_status":
            if getattr(self,"status_reply",None) is not None:return self.status_reply
            data=dict(state=self.state if self.sends else "none")
        else:data=dict(state="available",amount="1250.00",currency="USD")
        return SimpleNamespace(isError=False,structuredContent=data)
    def arm(self,*args):pass
    def cancel(self,*args):pass
    def confirm(self,*args):pass
    def submit(self,*args):self.sends+=1;return {"state":self.state}
    def confirm_and_send(self,*args):self.sends+=1;return {"state":self.state}
