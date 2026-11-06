"""Local Git-atomic delivery drill for the research Room.

Exercises the same fundamental transaction boundary used by production:
several files get published in ONE Git commit and stale/non-fast-forward
writers must not silently overwrite another conversation. The entire test
uses a *temporary local bare Git repository*, no GitHub push and no live
Room file. This test is not a production integration.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from room_endogenous_research_delivery import reconcile, initial_feed
from room_endogenous_transaction_store import initial_store, apply_cycle
from room_endogenous_goal_journal import new_journal
from room_endogenous_speech_option import parse
from room_endogenous_expression_v2 import choose_volunteers

PUBLIC=[{"speaker":"allen","id":"visit-1",
         "text":"How can we confirm both water cups really have the same volume?"}]
PRIVATE={"what_i_currently_believe":"A calibrated cylinder would help.",
         "belief_confidence":.5,"last_updated_cycle":0}


def _git(root,*args,check=True):
    p=subprocess.run(["git",*args],cwd=root,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,text=True,check=False)
    if check and p.returncode:
        raise AssertionError(f"local git command failed: {args!r}: {p.stderr[:300]}")
    return p


def _prepare():
    s=initial_store()
    proposal=parse(
        agent="mara",cycle=2,
        raw="I'd pour each cup into the same calibrated cylinder to compare volume.",
        public_history=PUBLIC,journal=new_journal("mara"),
        private_state=PRIVATE,consumed_ids=set())
    assert proposal["ok"]
    selection=choose_volunteers(cycle=2,public_history=PUBLIC,
        candidates={"mara":proposal},consumed_ids=set())
    state,changed=apply_cycle(s,expected_revision=0,cycle=2,
                              cycle_id="sim-cycle-2",candidates={"mara":proposal},
                              selected=selection,visitor_messages=PUBLIC)
    assert changed
    return state


def _stage(repo: Path, state: dict, feed: dict):
    # The state and public feed form one logical Git event boundary.
    path=repo/"research"
    path.mkdir(exist_ok=True)
    (path/"snapshot.json").write_text(json.dumps(state,sort_keys=True)+"\n")
    (path/"public.json").write_text(json.dumps(feed,sort_keys=True)+"\n")
    _git(repo,"add","research/snapshot.json","research/public.json")


def _seed(tmp):
    bare=Path(tmp)/"bare.git"
    _git(tmp,"init","--bare",str(bare))
    local=Path(tmp)/"base"
    _git(tmp,"clone",str(bare),str(local))
    _git(local,"config","user.email","experiment@invalid.local")
    _git(local,"config","user.name","Room research test")
    _stage(local,initial_store(),initial_feed())
    _git(local,"commit","-m","initial atomic research pair")
    _git(local,"branch","-M","main")
    _git(local,"push","origin","main")
    _git(bare,"symbolic-ref","HEAD","refs/heads/main")
    return bare,local


def test_one_git_commit_contains_state_and_publication_and_visitor():
    with tempfile.TemporaryDirectory() as folder:
        tmp=Path(folder)
        bare,local=_seed(tmp)
        state,feed,report=reconcile(_prepare(),initial_feed())
        _stage(local,state,feed)
        _git(local,"commit","-m","one research cognition and public event")
        _git(local,"push","origin","main")
        fresh=Path(folder)/"reader"
        _git(tmp,"clone",str(bare),str(fresh))
        durable=json.loads((fresh/"research/snapshot.json").read_text())
        public=json.loads((fresh/"research/public.json").read_text())
        assert len(public["conversation"])==1
        assert public["visitor_messages"]==PUBLIC
        assert durable["outbox"][0]["status"]=="delivered"
        assert durable["outbox"][0]["id"]==public["conversation"][0]["id"]


def test_two_git_writers_do_not_replace_each_other_without_recheck():
    with tempfile.TemporaryDirectory() as folder:
        tmp=Path(folder)
        bare,writer_a=_seed(tmp)
        writer_b=Path(folder)/"writer-b"
        _git(tmp,"clone",str(bare),str(writer_b))
        for writer in (writer_a,writer_b):
            _git(writer,"config","user.email","experiment@invalid.local")
            _git(writer,"config","user.name","Room research test")
        state,feed,_=reconcile(_prepare(),initial_feed())
        _stage(writer_a,state,feed)
        _git(writer_a,"commit","-m","writer A publishes visitor and model text")
        _git(writer_a,"push","origin","main")

        # This writer cannot silently reset the first writer's conversation.
        old_state=initial_store()
        old_state["last_cycle"]=3
        old_state["revision"]=1
        _stage(writer_b,old_state,initial_feed())
        _git(writer_b,"commit","-m","stale writer B tries different outcome")
        failed=_git(writer_b,"push","origin","main",check=False)
        assert failed.returncode!=0, "Git unexpectedly permitted a stale push"

        recovered=Path(folder)/"recover-from-remote"
        _git(tmp,"clone",str(bare),str(recovered))
        actual=json.loads((recovered/"research/public.json").read_text())
        assert len(actual["conversation"])==1
        assert actual["visitor_messages"]==PUBLIC


def test_git_commit_has_no_partial_research_file_visibility():
    with tempfile.TemporaryDirectory() as folder:
        tmp=Path(folder)
        bare,local=_seed(tmp)
        state,feed,_=reconcile(_prepare(),initial_feed())
        _stage(local,state,feed)
        _git(local,"commit","-m","atomic event")
        # Simulate a failure before pushing: the remote still has neither
        # change. A rerun from clean remote sees the same initial state.
        fresh=Path(folder)/"before-push"
        _git(tmp,"clone",str(bare),str(fresh))
        s=json.loads((fresh/"research/snapshot.json").read_text())
        f=json.loads((fresh/"research/public.json").read_text())
        assert s["revision"]==0
        assert not f["conversation"] and not f["visitor_messages"]
        # On success both files appear in the same new remote tree.
        _git(local,"push","origin","main")
        _git(fresh,"pull","--ff-only")
        assert json.loads((fresh/"research/snapshot.json").read_text())["revision"]>0
        assert len(json.loads((fresh/"research/public.json").read_text())["conversation"])==1


if __name__=="__main__":
    tests=[value for key,value in sorted(globals().copy().items())
           if key.startswith("test_") and callable(value)]
    for test in tests: test()
    print(f"PASS: {len(tests)} local Git-atomic Room publishing drills")
