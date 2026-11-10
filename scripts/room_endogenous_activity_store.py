#!/usr/bin/env python3
"""Crash-safe research-only persistence for the independent Room world.

The on-disk state is owned by this research subsystem, never room/state.json,
room/feed.json or the production relay. A per-file lock, version check, flush,
fsync and atomic rename prevent stale writers and partial local state. GitHub
push / remote viewer publication still require separate transaction protocols.
"""
from __future__ import annotations
import fcntl
import json
import os
import tempfile
from pathlib import Path
from room_endogenous_activity_society import SCHEMA as SOCIETY_SCHEMA
from room_endogenous_activity_world import _state_ok, _canonical, AGENTS
from room_endogenous_activity_goals import current_goal


def _guard_path(filename: Path):
    name=filename.name.casefold()
    if (name in {'state.json','feed.json','live.json','conversation.json',
                 'discourse.json','config.json'} or
            'room' in [p.casefold() for p in filename.parts[-2:-1]]):
        raise ValueError('activity world must not replace production Room data')


def _check(snapshot: dict) -> None:
    if (not isinstance(snapshot,dict) or snapshot.get('schema') != SOCIETY_SCHEMA
            or type(snapshot.get('revision')) is not int or snapshot['revision']<0
            or not _state_ok(snapshot.get('world'))
            or snapshot['revision']!=snapshot['world']['revision']
            or not isinstance(snapshot.get('cycles'),dict)
            or not isinstance(snapshot.get('conversation'),list)
            or not isinstance(snapshot.get('private_goals'),dict)
            or set(snapshot['private_goals']) != set(AGENTS)):
        raise ValueError('invalid activity society state')
    for owner in AGENTS:
        current_goal(snapshot['private_goals'][owner], owner)


def read_activity(path: str | Path) -> dict:
    file=Path(path)
    _guard_path(file)
    obj=json.loads(file.read_text(encoding='utf-8'))
    _check(obj)
    return obj


def commit_activity(path: str | Path, *, expected_revision: int,
                    candidate: dict, cycle_id: str) -> dict:
    """Commit exactly one research cycle or return unchanged idempotent retry."""
    file=Path(path)
    _guard_path(file)
    _check(candidate)
    if (type(expected_revision) is not int or expected_revision<0
            or not isinstance(cycle_id,str) or cycle_id not in candidate['cycles']
            or cycle_id not in candidate['world']['cycles']
            or candidate['revision']!=expected_revision+1):
        raise ValueError('misstated or skipped research cycle')
    file.parent.mkdir(parents=True, exist_ok=True)
    lock=file.with_suffix(file.suffix+'.lock')
    with lock.open('a+b') as hold:
        fcntl.flock(hold.fileno(),fcntl.LOCK_EX)
        if file.exists():
            current=json.loads(file.read_text(encoding='utf-8'))
            _check(current)
            if cycle_id in current['cycles']:
                if current==candidate:
                    return current
                raise ValueError('different content for same committed research cycle')
            if current['revision']!=expected_revision:
                raise ValueError('stale research commit')
            if candidate['world']['tick']!=current['world']['tick']+1:
                raise ValueError('not exactly one independently progressing world tick')
        elif expected_revision!=0:
            raise ValueError('missing prerequisite research state')
        data=(_canonical(candidate)+'\n').encode('utf-8')
        tempfile_name=None
        try:
            with tempfile.NamedTemporaryFile(dir=file.parent,prefix=file.name+'.',
                                             suffix='.tmp',delete=False) as tmp:
                tempfile_name=Path(tmp.name)
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tempfile_name,file)
            folder=os.open(file.parent,os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
        finally:
            if tempfile_name is not None and tempfile_name.exists():
                tempfile_name.unlink()
        return candidate